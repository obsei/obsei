"""``obsei.yaml``: declarative pipelines built only from registered plugins.

Secrets are never written in the file; plugins read them from the environment variables
the file names (``*_env`` fields).
"""

from __future__ import annotations

import os
from collections.abc import Collection
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, JsonValue, ValidationError, model_validator

from obsei.core.context import Context, LlmEndpoint
from obsei.core.registry import Registry
from obsei.enrichers import register as register_enrichers
from obsei.llm.egress import EgressPolicy
from obsei.pipeline import Pipeline, SourceSpec
from obsei.privacy.names import NamesConfig, redactor_for
from obsei.privacy.pseudonym import SALT_ENV_VAR, load_salt
from obsei.privacy.redact import ALL_REGIONS, Region
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
    sinks: list[PluginSpec] = Field(default_factory=list)
    batch_size: int = Field(default=100, ge=1)
    every_minutes: int | None = Field(
        default=None, ge=1, description="How often 'obsei serve' runs this pipeline."
    )


class ObseiConfig(_Strict):
    version: Literal[1] = 1
    store: StoreConfig = Field(default_factory=StoreConfig)
    privacy: PrivacyConfig = Field(default_factory=PrivacyConfig)
    egress: EgressPolicy | None = None
    llms: dict[str, LlmEndpoint] = Field(default_factory=dict)
    themes: ThemesConfig = Field(default_factory=ThemesConfig)
    ask_llm: str = Field(default="default", description="llms name used by ask and the Slack bot.")
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
            redactor=redactor_for(config.privacy.regions, config.privacy.names, ctx.egress)
            if config.privacy.redact
            else None,
            allow_unredacted=not config.privacy.redact,
            batch_size=spec.batch_size,
        )
    except ValidationError as exc:
        raise ConfigError(f"pipeline {name!r}: {exc}") from None
