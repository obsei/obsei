"""Citable, privacy-filtered views of records shared by MCP, Studio and the API."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from obsei.core.record import Record
from obsei.store import GroupBy

MAX_TEXT = 2000


class Evidence(BaseModel):
    id: str
    source: str
    instance: str
    url: str | None
    created_at: datetime
    rating: float | None
    lang: str | None
    text: str
    labels: dict[str, str]


class SearchResult(BaseModel):
    count: int
    items: list[Evidence]


class Stat(BaseModel):
    key: str | None
    count: int
    avg_rating: float | None


class StatsResult(BaseModel):
    group_by: GroupBy
    total: int
    groups: list[Stat]


def evidence(record: Record) -> Evidence:
    classify = record.enrichments.get("classify")
    value = classify.value if classify else None
    labels = (
        {k: v for k, v in value.items() if isinstance(v, str)} if isinstance(value, dict) else {}
    )
    text = record.text if len(record.text) <= MAX_TEXT else record.text[:MAX_TEXT] + "…"
    return Evidence(
        id=record.id,
        source=record.source.type,
        instance=record.source.instance,
        url=record.source.url,
        created_at=record.created_at,
        rating=record.rating,
        lang=record.lang or labels.get("language"),
        text=text,
        labels=labels,
    )


class ThemeInfo(BaseModel):
    id: str
    label: str | None
    description: str | None
    size: int
    duplicates: int
    avg_rating: float | None
    last_7_days: int
    previous_7_days: int
    sources: dict[str, int]
    languages: dict[str, int]
    intents: dict[str, int]
