"""Aggregate alerts: theme spikes, new themes, digests, the review queue and pipeline health.

Alerts read only k-anonymous theme summaries, so themes from fewer than ``k_anonymity`` people are
never reported. Each alert fires at most once per key (a theme id, ``digest``, ``review``, a
pipeline or a source) per cooldown, never while snoozed, and not for a week after an ack. Store
calls run under the optional ``lock``; sinks run outside it.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from contextlib import nullcontext
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from functools import partial
from statistics import fmean, pstdev

from pydantic import ValidationError

from obsei.config import AlertConfig, ConfigError, ObseiConfig, builtin_registry
from obsei.core.context import Context
from obsei.core.protocols import Alert, Alerts, Binds
from obsei.core.registry import Registry
from obsei.pipeline import Lock
from obsei.store import AlertState, Query, Store, ThemeSummary

ACK = timedelta(days=7)
WEEK = timedelta(days=7)
MAX_QUOTE = 280


@dataclass(frozen=True)
class Fired:
    alert: Alert
    errors: list[str] = field(default_factory=list)


def spike(theme: ThemeSummary, sensitivity: float, min_count: int) -> tuple[float, float] | None:
    """(z-score, weekly mean of the seven weeks before) when the last seven days spike: at least
    ``min_count`` records, ``sensitivity`` standard deviations (at least 1) above the mean, and
    rising (double the week before)."""
    *history, count = theme.weekly
    mean = fmean(history)
    z = (count - mean) / max(pstdev(history), 1.0)
    if count >= min_count and z >= sensitivity and theme.rising:
        return z, mean
    return None


def cooldown(alert: AlertConfig) -> timedelta | None:
    """None: once per key."""
    if alert.kind == "new_theme":
        return None
    if alert.kind == "digest":
        return timedelta(days=alert.period_days)
    return timedelta(hours=alert.cooldown_hours or (168 if alert.kind == "theme_spike" else 24))


def due(state: AlertState | None, wait: timedelta | None, now: datetime) -> bool:
    if state is None:
        return True
    if state.snoozed_until and state.snoozed_until > now:
        return False
    if state.acked_at and now - state.acked_at < ACK:
        return False
    if state.last_fired_at is None:
        return True
    return wait is not None and now - state.last_fired_at >= wait


def _quote(text: str) -> str:
    flat = " ".join(text.split())
    return flat if len(flat) <= MAX_QUOTE else flat[:MAX_QUOTE] + "…"


def _sources(theme: ThemeSummary) -> list[str]:
    counts = ", ".join(f"{k} {v}" for k, v in theme.sources.items())
    return [f"Sources: {counts}"] if counts else []


def _name(theme: ThemeSummary) -> str:
    return theme.label or theme.id


def _found(
    alert: AlertConfig,
    config: ObseiConfig,
    store: Store,
    *,
    themes: list[ThemeSummary],
    failures: Mapping[str, str],
    now: datetime,
) -> Iterator[Alert]:
    make = partial(Alert, alert=alert.name, kind=alert.kind, owner=alert.owner)

    def quotes(theme_id: str) -> list[str]:
        return [_quote(q) for q in store.theme_samples(theme_id, alert.quotes)]

    if alert.kind == "new_theme":
        for theme in (t for t in themes if t.size == t.last_7_days):
            yield make(
                key=theme.id,
                theme=theme.id,
                title=f"New theme: {_name(theme)}",
                lines=[f"{theme.size} records, all from the last 7 days", *_sources(theme)],
                count=theme.size,
                quotes=quotes(theme.id),
            )
    elif alert.kind == "theme_spike":
        for theme in themes:
            found = spike(theme, alert.sensitivity, alert.min_count)
            if found:
                z, mean = found
                yield make(
                    key=theme.id,
                    theme=theme.id,
                    title=f"Theme spiking: {_name(theme)}",
                    lines=[
                        f"{theme.last_7_days} records in the last 7 days against {mean:.1f} a "
                        f"week over the 7 weeks before (z = {z:.1f})",
                        *_sources(theme),
                    ],
                    count=theme.last_7_days,
                    baseline=round(mean, 2),
                    quotes=quotes(theme.id),
                )
    elif alert.kind == "digest":
        start = now - timedelta(days=alert.period_days)
        total = sum(r.count for r in store.stats(Query(since=start), "source", limit=1000))
        counts = store.theme_counts(start)
        top = sorted((t for t in themes if t.id in counts), key=lambda t: -counts[t.id])
        yield make(
            key="digest",
            title=f"Feedback digest: the last {alert.period_days} days",
            lines=[
                f"{total} records",
                *(
                    f"{_name(t)}: {counts[t.id]}" + (" (rising)" if t.rising else "")
                    for t in top[: alert.top]
                ),
            ],
            count=total,
        )
    elif alert.kind == "review_queue":
        pending = store.review_count(now - WEEK)
        if pending >= alert.min_pending:
            yield make(
                key="review",
                title=f"{pending} records await review",
                lines=[f"{pending} records from the last 7 days were marked for review"],
                count=pending,
            )
    else:
        for pipeline, error in failures.items():
            yield make(key=pipeline, title=f"Pipeline {pipeline} failed", lines=[error])
        names = {p.name for p in config.pipelines}
        hours = alert.stale_hours
        for pipeline, source, moved in store.cursor_times() if hours else ():
            if pipeline in names and now - moved >= timedelta(hours=hours or 0):
                yield make(
                    key=f"{pipeline}/{source}",
                    title=f"Source {pipeline}/{source} fetched nothing for {hours} h",
                    lines=[f"Last fetched {moved:%Y-%m-%d %H:%M} UTC"],
                )


def pending(
    config: ObseiConfig,
    store: Store,
    states: Mapping[tuple[str, str], AlertState],
    failures: Mapping[str, str],
    now: datetime,
) -> list[tuple[AlertConfig, Alert]]:
    """Alerts whose condition holds and that are not cooling down, snoozed or acked."""
    themes = (
        store.theme_summaries(min_size=config.themes.k_anonymity, now=now)
        if any(a.kind in ("theme_spike", "new_theme", "digest") for a in config.alerts)
        else []
    )
    return [
        (alert, found.model_copy(update={"lines": [*found.lines, f"Owner: {alert.owner}"]}))
        if alert.owner
        else (alert, found)
        for alert in config.alerts
        for found in _found(alert, config, store, themes=themes, failures=failures, now=now)
        if due(states.get((alert.name, found.key)), cooldown(alert), now)
    ]


def alert_sinks(alert: AlertConfig, ctx: Context, registry: Registry) -> list[tuple[str, Alerts]]:
    built: list[tuple[str, Alerts]] = []
    for target in alert.to:
        try:
            sink = registry.sink(target.type).create(target.config, ctx)
        except ValidationError as exc:
            raise ConfigError(f"alert {alert.name!r}, sink {target.name!r}: {exc}") from None
        if not isinstance(sink, Alerts):
            raise ConfigError(
                f"alert {alert.name!r}: {target.type} sinks cannot deliver alerts; "
                "use webhook, slack, notify or teams"
            )
        if isinstance(sink, Binds):
            sink.bind(f"alerts/{alert.name}", target.name)
        built.append((target.name, sink))
    return built


def check_alerts(
    config: ObseiConfig,
    ctx: Context,
    store: Store,
    *,
    failures: Mapping[str, str] | None = None,
    now: datetime | None = None,
    dry_run: bool = False,
    lock: Lock | None = None,
) -> list[Fired]:
    """Deliver every due alert; ``failures`` maps pipelines that just failed to their error."""
    if not config.alerts:
        return []
    guard: Lock = lock or nullcontext()
    moment = now or datetime.now(UTC)
    with guard:
        states = {(s.alert, s.key): s for s in store.alert_states()}
        found = pending(config, store, states, failures or {}, moment)
    if dry_run:
        return [Fired(alert) for _, alert in found]
    registry = builtin_registry(config.plugins)
    sinks: dict[str, list[tuple[str, Alerts]]] = {}
    fired: list[Fired] = []
    for alert, message in found:
        if alert.name not in sinks:
            sinks[alert.name] = alert_sinks(alert, ctx, registry)
        errors: list[str] = []
        sent = False
        for key, sink in sinks[alert.name]:
            result = sink.alert(message)
            errors.extend(f"{key}: {error}" for error in result.errors)
            sent = sent or not result.errors
            if result.deliveries:
                with guard:
                    store.log_deliveries(f"alerts/{alert.name}", key, result.deliveries)
        if sent:
            state = states.get((alert.name, message.key)) or AlertState(
                alert=alert.name, key=message.key
            )
            with guard:
                store.put_alert_state(state.model_copy(update={"last_fired_at": moment}))
        fired.append(Fired(message, errors))
    return fired
