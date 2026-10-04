"""Helpers shared by built-in sources."""

from __future__ import annotations

import hashlib
import html
import re
from collections.abc import Iterator, Mapping
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from typing import Literal, TypeAlias

from pydantic import BaseModel, ConfigDict, Field, JsonValue

from obsei.core.context import Context
from obsei.core.protocols import Cursor
from obsei.core.record import Record, SourceRef

TextFormat: TypeAlias = Literal["plain", "html"]

_TAG = re.compile(r"<[^>]+>")
_BLOCK = re.compile(r"<\s*(br|/p|/div|/li|/h[1-6])\b[^>]*>", re.IGNORECASE)


def html_to_text(value: str) -> str:
    text = _TAG.sub("", _BLOCK.sub("\n", value))
    lines = (" ".join(line.split()) for line in html.unescape(text).splitlines())
    return "\n".join(line for line in lines if line)


def parse_time(value: JsonValue) -> datetime | None:
    """ISO 8601, RFC 2822 or epoch seconds; naive values are taken as UTC."""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, int | float):
        try:
            return datetime.fromtimestamp(value, UTC)
        except (OverflowError, OSError, ValueError):
            return None
    if not isinstance(value, str) or not value.strip():
        return None
    raw = value.strip()
    parsed: datetime | None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        try:
            parsed = parsedate_to_datetime(raw)
        except (TypeError, ValueError):
            return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def lookup(item: JsonValue, path: str) -> JsonValue:
    """Dotted path lookup; numeric segments index into lists."""
    current = item
    for part in path.split("."):
        if isinstance(current, Mapping):
            current = current.get(part)
        elif isinstance(current, list) and part.isdigit() and int(part) < len(current):
            current = current[int(part)]
        else:
            return None
    return current


def as_text(value: JsonValue) -> str | None:
    if value is None or isinstance(value, dict | list):
        return None
    text = str(value).strip()
    return text or None


def as_float(value: JsonValue) -> float | None:
    if value is None or isinstance(value, bool | dict | list):
        return None
    try:
        return float(value)
    except ValueError:
        return None


class FieldMap(BaseModel):
    """Where to find record fields in a row or JSON item (dotted paths for nested JSON)."""

    model_config = ConfigDict(extra="forbid")

    text: str | list[str] = "text"
    id: str | None = "id"
    created_at: str | None = "created_at"
    rating: str | None = None
    author: str | None = None
    lang: str | None = None
    url: str | None = None
    context: list[str] = Field(default_factory=list)


def map_item(
    item: JsonValue,
    fields: FieldMap,
    *,
    source_type: str,
    instance: str,
    ctx: Context,
    fallback_id: str | None = None,
    default_time: datetime,
    text_format: TextFormat = "plain",
) -> Record | None:
    """Build a record from a row; returns None when the row has no text."""
    paths = [fields.text] if isinstance(fields.text, str) else fields.text
    parts = [t for t in (as_text(lookup(item, p)) for p in paths) if t]
    if text_format == "html":
        parts = [t for t in map(html_to_text, parts) if t]
    if not parts:
        return None
    text = "\n\n".join(parts)
    native_id = (
        (as_text(lookup(item, fields.id)) if fields.id else None)
        or fallback_id
        or f"sha_{hashlib.sha256(text.encode()).hexdigest()[:32]}"
    )
    created = parse_time(lookup(item, fields.created_at)) if fields.created_at else None
    lang = as_text(lookup(item, fields.lang)) if fields.lang else None
    context = {
        key: value for key in fields.context if (value := as_text(lookup(item, key))) is not None
    }
    return Record(
        source=SourceRef(
            type=source_type,
            instance=instance,
            native_id=native_id,
            url=as_text(lookup(item, fields.url)) if fields.url else None,
        ),
        text=text,
        created_at=created or default_time,
        author=ctx.author(as_text(lookup(item, fields.author)) if fields.author else None, lang),
        rating=as_float(lookup(item, fields.rating)) if fields.rating else None,
        lang=lang,
        context=context,
    )


def stamp(record: Record) -> str:
    return record.created_at.astimezone(UTC).isoformat()


def oldest_first(records: list[Record], state: Cursor, key: str) -> Iterator[tuple[Record, Cursor]]:
    """Yield oldest first; the cursor moves to the newest stamp only with the final record."""
    if not records:
        return
    ordered = sorted(records, key=stamp)
    for record in ordered[:-1]:
        yield record, dict(state)
    state[key] = stamp(ordered[-1])
    yield ordered[-1], dict(state)
