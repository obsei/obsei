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


TITLE_LENGTH = 80


def marker(record: Record) -> str:
    return f"obsei:{record.id}"


def title(record: Record) -> str:
    first = record.text.strip().splitlines()[0] if record.text.strip() else record.id
    intent = label(record, "classify.intent")
    prefix = f"[{intent}] " if intent else ""
    return prefix + (first[:TITLE_LENGTH] + "…" if len(first) > TITLE_LENGTH else first)


def body(record: Record) -> str:
    lines = [f"> {line}" for line in record.text.splitlines()]
    meta = [f"source: `{record.source.type}/{record.source.instance}`"]
    if record.rating is not None:
        meta.append(f"rating: {record.rating:g}")
    if record.source.url:
        meta.append(f"[original]({record.source.url})")
    return "\n".join([*lines, "", " · ".join(meta), "", f"<!-- {marker(record)} -->"])
