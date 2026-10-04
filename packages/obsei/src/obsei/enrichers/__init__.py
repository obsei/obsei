from obsei.core.plugin import factory
from obsei.core.registry import Registry
from obsei.enrichers.classify import (
    Cascade,
    Classification,
    ClassifierConfig,
    ClassifyPluginConfig,
    DecisionClassification,
    DecisionClassifier,
    FieldSpec,
    LlmClassifier,
    build_classifier,
    build_schema,
)
from obsei.enrichers.filter import DecisionFilter, FilterConfig, build_filter


def register(registry: Registry) -> None:
    registry.add_enricher("classify", factory(ClassifyPluginConfig, build_classifier))
    registry.add_enricher("filter", factory(FilterConfig, build_filter))


__all__ = [
    "Cascade",
    "Classification",
    "ClassifierConfig",
    "ClassifyPluginConfig",
    "DecisionClassification",
    "DecisionClassifier",
    "DecisionFilter",
    "FieldSpec",
    "FilterConfig",
    "LlmClassifier",
    "build_schema",
    "register",
]
