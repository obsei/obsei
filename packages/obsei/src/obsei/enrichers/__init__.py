from obsei.core.plugin import factory
from obsei.core.registry import Registry
from obsei.enrichers.classify import (
    Cascade,
    Classification,
    ClassifierConfig,
    ClassifyPluginConfig,
    FieldSpec,
    LlmClassifier,
    build_classifier,
    build_schema,
)


def register(registry: Registry) -> None:
    registry.add_enricher("classify", factory(ClassifyPluginConfig, build_classifier))


__all__ = [
    "Cascade",
    "Classification",
    "ClassifierConfig",
    "FieldSpec",
    "LlmClassifier",
    "build_schema",
    "register",
]
