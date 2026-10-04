from __future__ import annotations

import os

from obsei.core.record import Record


class SinkConfigError(RuntimeError):
    pass


def env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise SinkConfigError(f"{name} is not set")
    return value


def label(record: Record, name: str) -> str | None:
    """A string field of an enrichment value, e.g. ``label(r, "classify.intent")``."""
    enricher, _, key = name.partition(".")
    enrichment = record.enrichments.get(enricher)
    if enrichment is None:
        return None
    value = enrichment.value
    if key and isinstance(value, dict):
        value = value.get(key)
    return value if isinstance(value, str) else None


def matches(record: Record, when: dict[str, list[str]], max_rating: float | None) -> bool:
    if max_rating is not None and (record.rating is None or record.rating > max_rating):
        return False
    return all(label(record, name) in allowed for name, allowed in when.items())
