"""Every example config in examples/ must load with the real loader and name real plugins."""

from importlib.metadata import entry_points
from pathlib import Path

import pytest
from pydantic import BaseModel

from obsei.config import ObseiConfig, PluginSpec, builtin_registry, load_config
from obsei.core.plugin import Factory
from obsei.core.registry import ENTRY_POINT_GROUP

EXAMPLES = Path(__file__).resolve().parents[3] / "examples"
FILES = sorted(EXAMPLES.rglob("*.yaml"))
INSTALLED = {ep.name for ep in entry_points(group=ENTRY_POINT_GROUP)}


def _validated(factory: Factory[object], spec: PluginSpec) -> BaseModel:
    return factory.config_model.model_validate(spec.config)


def _check_llm(config: ObseiConfig, name: str | None, where: str) -> None:
    if name is not None:
        assert name in config.llms, f"{where}: no llms entry named {name!r}"


def test_examples_exist() -> None:
    names = {p.name for p in FILES}
    assert {"social-listening.yaml", "enterprise-air-gapped.yaml"} <= names


@pytest.mark.parametrize("path", FILES, ids=lambda p: str(p.relative_to(EXAMPLES)))
def test_example_is_valid(path: Path) -> None:
    config = load_config(path)
    missing = sorted(set(config.plugins) - INSTALLED)
    if missing:
        pytest.skip(f"needs plugins that are not installed: {', '.join(missing)}")
    registry = builtin_registry(config.plugins)

    for pipeline in config.pipelines:
        keys = [s.key for s in pipeline.sources]
        assert len(keys) == len(set(keys)), f"{pipeline.name}: duplicate source keys"
        for source in pipeline.sources:
            _validated(registry.source(source.type), source)
        for enricher in pipeline.enrichers:
            model = _validated(registry.enricher(enricher.type), enricher)
            where = f"{pipeline.name}/{enricher.type}"
            _check_llm(config, getattr(model, "llm", None), where)
            _check_llm(config, getattr(model, "fallback_llm", None), where)
        for sink in pipeline.sinks:
            _validated(registry.sink(sink.type), sink)
        pipeline.router()

    themes = config.themes
    _check_llm(config, themes.labeler, "themes.labeler")
    if themes.embedder != "hashing" and not themes.embedder.startswith("local"):
        _check_llm(config, themes.embedder, "themes.embedder")
        assert config.llms[themes.embedder].embedding_model, "themes.embedder needs embedding_model"
    if config.llms:
        _check_llm(config, config.ask_llm, "ask_llm")


def test_unknown_keys_are_rejected(tmp_path: Path) -> None:
    good = (EXAMPLES / "social-listening.yaml").read_text(encoding="utf-8")
    bad = tmp_path / "bad.yaml"
    bad.write_text(good.replace("text_format: html", "text_fromat: html"), encoding="utf-8")
    config = load_config(bad)
    registry = builtin_registry()
    mastodon = next(s for s in config.pipelines[0].sources if s.key == "mastodon")
    with pytest.raises(ValueError, match="text_fromat"):
        _validated(registry.source(mastodon.type), mastodon)
