"""Run pipelines with failures isolated, once or on a schedule inside ``obsei serve``."""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable, Sequence
from contextlib import AbstractContextManager
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from obsei.config import ConfigError, ObseiConfig, build_pipeline
from obsei.core.context import Context
from obsei.core.registry import PluginError
from obsei.pipeline import PipelineError, RunReport, run
from obsei.store import Store
from obsei.themes import update_themes

log = logging.getLogger("obsei")
RUN_ERRORS = (ConfigError, PipelineError, PluginError, OSError, RuntimeError, ValueError)
StoreLease = Callable[[], AbstractContextManager[Store]]


@dataclass(frozen=True)
class Outcome:
    pipeline: str
    started_at: datetime
    report: RunReport | None = None
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.error is None

    def summary(self) -> str:
        if self.report is None:
            return f"{self.pipeline}: failed: {self.error}"
        r = self.report
        sent = ", ".join(f"{k}={v}" for k, v in r.sent.items()) or "none"
        return (
            f"{self.pipeline}: fetched {r.fetched}, stored {r.stored}, "
            f"enriched {sum(r.enriched.values())}, sent {sent}"
        )


def run_pipelines(
    config: ObseiConfig, ctx: Context, store: Store, names: Sequence[str]
) -> list[Outcome]:
    """Run each pipeline in turn; a failure is recorded and the next pipeline still runs."""
    outcomes: list[Outcome] = []
    for name in names:
        started = datetime.now(UTC)
        try:
            report = run(build_pipeline(config, name, ctx), store)
        except RUN_ERRORS as exc:
            log.warning("pipeline %s failed: %s", name, exc)
            outcomes.append(Outcome(name, started, error=str(exc)))
            continue
        outcomes.append(Outcome(name, started, report=report))
    return outcomes


def refresh_themes(config: ObseiConfig, ctx: Context, store: Store) -> None:
    settings = config.themes
    labeler = ctx.chat(settings.labeler) if settings.labeler else None
    update_themes(store, ctx.embedder(settings.embedder), settings, labeler)


@dataclass
class Scheduler:
    """Runs pipelines that set ``every_minutes`` from inside ``obsei serve``, sharing its store.

    DuckDB allows one writer, so a separate ``obsei run`` cannot use a database that a running
    server holds; scheduling here avoids that.
    """

    config: ObseiConfig
    ctx: Context
    lease: StoreLease
    tick_seconds: float = 30.0
    last: dict[str, Outcome] = field(default_factory=dict)
    _due: dict[str, datetime] = field(default_factory=dict)
    _stop: threading.Event = field(default_factory=threading.Event)
    _thread: threading.Thread | None = None

    def scheduled(self) -> dict[str, int]:
        return {p.name: p.every_minutes for p in self.config.pipelines if p.every_minutes}

    def due(self, now: datetime) -> list[str]:
        return [name for name in self.scheduled() if self._due.get(name, now) <= now]

    def run_due(self, now: datetime | None = None) -> list[Outcome]:
        moment = now or datetime.now(UTC)
        names = self.due(moment)
        if not names:
            return []
        with self.lease() as store:
            outcomes = run_pipelines(self.config, self.ctx, store, names)
            if self.config.themes.auto and any(o.ok for o in outcomes):
                try:
                    refresh_themes(self.config, self.ctx, store)
                except (*RUN_ERRORS, KeyError) as exc:
                    log.warning("theme update failed: %s", exc)
        schedule = self.scheduled()
        for outcome in outcomes:
            self.last[outcome.pipeline] = outcome
            self._due[outcome.pipeline] = moment + timedelta(minutes=schedule[outcome.pipeline])
            log.info(outcome.summary())
        return outcomes

    def _loop(self) -> None:
        while not self._stop.is_set():
            self.run_due()
            self._stop.wait(self.tick_seconds)

    def start(self) -> None:
        if self.scheduled() and self._thread is None:
            self._thread = threading.Thread(target=self._loop, name="obsei-scheduler", daemon=True)
            self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=60)
