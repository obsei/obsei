from __future__ import annotations

import os
from collections.abc import Mapping

from pydantic import JsonValue

from obsei.core.record import Record
from obsei.routing import When, text


class SinkConfigError(RuntimeError):
    pass


def env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise SinkConfigError(f"{name} is not set")
    return value


def label(record: Record, name: str) -> str | None:
    """A string or yes/no field of an enrichment value, e.g. ``label(r, "classify.intent")`` or
    ``label(r, "classify.fields.urgency")``; yes/no reads as ``"true"`` or ``"false"``."""
    enricher, _, path = name.partition(".")
    enrichment = record.enrichments.get(enricher)
    if enrichment is None:
        return None
    value = enrichment.value
    for key in path.split(".") if path else ():
        value = value.get(key) if isinstance(value, dict) else None
    return text(value)


def matches(record: Record, when: Mapping[str, object], max_rating: float | None) -> bool:
    """Whether ``record`` passes a sink's ``when`` filter; see :mod:`obsei.routing`."""
    return When.parse(when, max_rating=max_rating).matches(record)


def intents(*names: str) -> dict[str, JsonValue]:
    """A ``when`` filter that keeps the given classify intents."""
    return {"classify.intent": list(names)}


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
