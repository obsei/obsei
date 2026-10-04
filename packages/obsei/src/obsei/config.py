"""``obsei.yaml``: declarative pipelines built only from registered plugins.

Secrets are never written in the file; plugins read them from the environment variables
the file names (``*_env`` fields).
"""

from __future__ import annotations

import os
from collections.abc import Collection, Sequence
from pathlib import Path
from typing import Literal, Self

import yaml
from pydantic import BaseModel, ConfigDict, Field, JsonValue, ValidationError, model_validator

from obsei.access import AccessConfig
from obsei.core.context import Context, LlmEndpoint
from obsei.core.registry import Registry
from obsei.enrichers import register as register_enrichers
from obsei.enrichers.classify import ClassifyPluginConfig
from obsei.llm.egress import EgressPolicy
from obsei.pipeline import Pipeline, SourceSpec
from obsei.privacy.names import NamesConfig, redactor_for
from obsei.privacy.pseudonym import SALT_ENV_VAR, load_salt
from obsei.privacy.redact import ALL_REGIONS, Region
from obsei.routing import UNROUTED, Route, Router, When
from obsei.sinks import register as register_sinks
from obsei.sources import register as register_sources
from obsei.themes import ThemesConfig

DEFAULT_PATH = Path("obsei.yaml")


class ConfigError(ValueError):
    pass


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PluginSpec(_Strict):
    type: str
    config: dict[str, JsonValue] = Field(default_factory=dict)


class SourceEntry(PluginSpec):
    key: str = Field(pattern=r"^[\w-]+$")


class SinkEntry(PluginSpec):
    key: str | None = Field(
        default=None, pattern=r"^[\w-]+$", description="Name routes refer to; default: the type."
    )

    @property
    def name(self) -> str:
        return self.key or self.type


CONDITION_SINKS = frozenset({"slack", "jira", "linear", "github_issues"})
"""Built-in sinks whose ``when`` is checked on load."""


class RouteRule(_Strict):
    """One of: ``when`` with ``sinks``; ``review`` (records still flagged for review); or
    ``default`` (every record no earlier rule matched), which must come last."""

    name: str | None = Field(default=None, pattern=r"^[\w-]+$")
    when: dict[str, JsonValue] | None = None
    sinks: list[str] | None = None
    review: list[str] | None = None
    default: list[str] | None = None

    @model_validator(mode="after")
    def _one_kind(self) -> Self:
        kinds = [k for k in ("when", "review", "default") if getattr(self, k) is not None]
        if len(kinds) != 1:
            raise ValueError("a route needs exactly one of when (with sinks), review or default")
        if (self.when is None) != (self.sinks is None):
            raise ValueError("when and sinks go together")
        return self

    @property
    def targets(self) -> list[str]:
        return self.sinks or self.review or self.default or []

    @property
    def label(self) -> str:
        if self.name:
            return self.name
        if self.review is not None:
            return "review"
        if self.default is not None:
            return "default"
        return "+".join(self.targets) or "none"

    def conditions(self, levels: dict[str, Sequence[str]] | None = None) -> When:
        if self.review is not None:
            return When(review=True)
        return When.parse(self.when, levels=levels)


class PrivacyConfig(_Strict):
    redact: bool = True
    regions: list[Region] = Field(default_factory=lambda: list(ALL_REGIONS))
    names: NamesConfig = Field(default_factory=NamesConfig)


class StoreConfig(_Strict):
    path: Path = Path("obsei.duckdb")
    unencrypted: bool = False


class PipelineConfig(_Strict):
    name: str = Field(pattern=r"^[\w-]+$")
    sources: list[SourceEntry] = Field(min_length=1)
    enrichers: list[PluginSpec] = Field(default_factory=list)
    sinks: list[SinkEntry] = Field(default_factory=list)
    route: list[RouteRule] | None = Field(
        default=None,
        min_length=1,
        description="Ordered routes; the first match decides which named sinks get a record.",
    )
    batch_size: int = Field(default=100, ge=1)
    every_minutes: int | None = Field(
        default=None, ge=1, description="How often 'obsei serve' runs this pipeline."
    )

    def answers(self) -> dict[str, list[str] | None]:
        """Paths the pipeline's classifier answers, with the levels of score fields."""
        for enricher in self.enrichers:
            if enricher.type != "classify":
                continue
            try:
                classify = ClassifyPluginConfig.model_validate(enricher.config)
            except ValidationError:
                return {}
            paths: dict[str, list[str] | None] = {
                "classify.sentiment": None,
                "classify.intent": None,
            }
            for name, spec in classify.fields.items():
                paths[f"classify.fields.{name}"] = spec.levels if spec.kind == "score" else None
            return paths
        return {}

    def _levels(self) -> dict[str, Sequence[str]]:
        return {path: levels for path, levels in self.answers().items() if levels}

    @model_validator(mode="after")
    def _sinks_and_routes(self) -> Self:
        names = [s.name for s in self.sinks]
        duplicated = {n for n in names if names.count(n) > 1}
        explicit = {s.key for s in self.sinks if s.key}
        if duplicated and (self.route is not None or duplicated & explicit):
            raise ValueError(
                f"pipeline {self.name!r}: sink keys must be unique; give sinks of the same type "
                f"a key: {sorted(duplicated)}"
            )
        answers = self.answers()
        for sink in self.sinks:
            when = sink.config.get("when")
            if sink.type in CONDITION_SINKS and isinstance(when, dict):
                try:
                    When.parse(when).check_levels(answers)
                except ValueError as exc:
                    raise ValueError(
                        f"pipeline {self.name!r}, sink {sink.name!r}: when.{exc}"
                    ) from None
        self._check_routes(set(names), answers)
        return self

    def _check_routes(self, sinks: set[str], answers: dict[str, list[str] | None]) -> None:
        seen: set[str] = set()
        for position, rule in enumerate(self.route or [], start=1):
            where = f"pipeline {self.name!r}, route {position}" + (
                f" ({rule.name})" if rule.name else ""
            )
            if rule.default is not None and position != len(self.route or []):
                raise ValueError(f"{where}: default must be the last route")
            unknown = sorted(set(rule.targets) - sinks)
            if unknown:
                raise ValueError(f"{where}: no sink with key {unknown}; sinks are {sorted(sinks)}")
            if rule.name in seen or rule.name == UNROUTED:
                raise ValueError(f"{where}: route names must be unique and not {UNROUTED!r}")
            if rule.name:
                seen.add(rule.name)
            try:
                rule.conditions().check_levels(answers)
            except ValueError as exc:
                raise ValueError(f"{where}: when.{exc}") from None

    def router(self) -> Router | None:
        if self.route is None:
            return None
        levels = self._levels()
        return Router(
            tuple(Route(r.label, tuple(r.targets), r.conditions(levels)) for r in self.route)
        )


class ObseiConfig(_Strict):
    version: Literal[1] = 1
    store: StoreConfig = Field(default_factory=StoreConfig)
    privacy: PrivacyConfig = Field(default_factory=PrivacyConfig)
    egress: EgressPolicy | None = None
    llms: dict[str, LlmEndpoint] = Field(default_factory=dict)
    themes: ThemesConfig = Field(default_factory=ThemesConfig)
    access: AccessConfig = Field(default_factory=AccessConfig)
    ask_llm: str = Field(default="default", description="llms name used by ask and the Slack bot.")
    ask_judge: str | None = Field(
        default=None,
        description="llms name of a decision endpoint that checks answers against the cited "
        "records.",
    )
    ask_judge_threshold: float = Field(
        default=0.5, ge=0.0, le=1.0, description="Below this, answers are flagged unsupported."
    )
    plugins: list[str] = Field(
        default_factory=list, description="Installed plugin entry points allowed to load."
    )
    pipelines: list[PipelineConfig] = Field(min_length=1)

    @model_validator(mode="after")
    def _unique_names(self) -> ObseiConfig:
        names = [p.name for p in self.pipelines]
        if len(names) != len(set(names)):
            raise ValueError("pipeline names must be unique")
        return self

    @model_validator(mode="after")
    def _judge_is_decision_model(self) -> ObseiConfig:
        judge = self.llms.get(self.ask_judge) if self.ask_judge else None
        if self.ask_judge and (judge is None or judge.api != "decision"):
            raise ValueError(
                f"ask_judge {self.ask_judge!r} must name an llms entry with api: decision"
            )
        return self

    def pipeline(self, name: str) -> PipelineConfig:
        for candidate in self.pipelines:
            if candidate.name == name:
                return candidate
        raise ConfigError(f"no pipeline named {name!r}")


def load_config(path: Path = DEFAULT_PATH) -> ObseiConfig:
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise ConfigError(f"{path} not found; run 'obsei init' to create one") from None
    except yaml.YAMLError as exc:
        raise ConfigError(f"{path}: invalid YAML: {exc}") from None
    try:
        return ObseiConfig.model_validate(raw)
    except ValidationError as exc:
        raise ConfigError(f"{path}: {exc}") from None


def builtin_registry(allow: Collection[str] = ()) -> Registry:
    registry = Registry()
    register_sources(registry)
    register_enrichers(registry)
    register_sinks(registry)
    if allow:
        registry.load_entry_points(allow=allow)
    return registry


def build_context(config: ObseiConfig) -> Context:
    return Context(
        egress=config.egress or EgressPolicy.from_env(),
        salt=load_salt() if os.environ.get(SALT_ENV_VAR) else None,
        llms=config.llms,
    )


def build_pipeline(
    config: ObseiConfig,
    name: str,
    ctx: Context,
    registry: Registry | None = None,
    *,
    with_sinks: bool = True,
) -> Pipeline:
    registry = registry or builtin_registry(config.plugins)
    spec = config.pipeline(name)
    try:
        return Pipeline(
            name=spec.name,
            sources=[
                SourceSpec(s.key, registry.source(s.type).create(s.config, ctx))
                for s in spec.sources
            ],
            enrichers=[registry.enricher(e.type).create(e.config, ctx) for e in spec.enrichers],
            sinks=[registry.sink(s.type).create(s.config, ctx) for s in spec.sinks]
            if with_sinks
            else [],
            sink_keys=[s.name for s in spec.sinks] if with_sinks else [],
            router=spec.router() if with_sinks else None,
            redactor=redactor_for(config.privacy.regions, config.privacy.names, ctx.egress)
            if config.privacy.redact
            else None,
            allow_unredacted=not config.privacy.redact,
            batch_size=spec.batch_size,
        )
    except ValidationError as exc:
        raise ConfigError(f"pipeline {name!r}: {exc}") from None
