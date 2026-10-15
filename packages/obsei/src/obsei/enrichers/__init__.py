from obsei.core.plugin import Catalog, factory
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
    registry.add_enricher(
        "classify",
        factory(
            ClassifyPluginConfig,
            build_classifier,
            Catalog(
                title="Sentiment, intent and your own questions",
                category="enrich",
                status="verified",
                docs_url="https://docs.obsei.com/guides/classify/",
            ),
        ),
    )
    registry.add_enricher(
        "filter",
        factory(
            FilterConfig,
            build_filter,
            Catalog(
                title="Yes/no filter (spam, off-topic)",
                category="enrich",
                docs_url="https://docs.obsei.com/configuration/#enrichers",
            ),
        ),
    )


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
