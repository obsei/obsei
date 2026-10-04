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
    fields: dict[str, str | bool] = {}
    confidences: dict[str, float] = {}
    review: bool | None = None


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
    fields, confidences, review = _decision(value)
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
        fields=fields,
        confidences=confidences,
        review=review,
    )


def _decision(value: object) -> tuple[dict[str, str | bool], dict[str, float], bool | None]:
    """Field answers, per-question confidences and the review flag of a classify value."""
    if not isinstance(value, dict):
        return {}, {}, None
    fields, confidences, review = (value.get(k) for k in ("fields", "confidences", "review"))
    return (
        {k: v for k, v in fields.items() if isinstance(v, str | bool)}
        if isinstance(fields, dict)
        else {},
        {k: float(v) for k, v in confidences.items() if isinstance(v, int | float)}
        if isinstance(confidences, dict)
        else {},
        review if isinstance(review, bool) else None,
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
    weekly: list[int] = []
