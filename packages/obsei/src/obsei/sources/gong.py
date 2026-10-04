"""Gong call transcripts: only what customers (external speakers) said, one record per call."""

from __future__ import annotations

import os
from collections.abc import Iterator
from datetime import UTC, datetime
from typing import ClassVar

import httpx
from pydantic import BaseModel, ConfigDict, Field, JsonValue

from obsei.core.context import Context
from obsei.core.protocols import Cursor
from obsei.core.record import Record, SourceRef
from obsei.sources._common import as_text, lookup, parse_time, stamp


class GongConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    base_url: str = Field(default="https://api.gong.io", description="Your Gong API base URL.")
    access_key_env: str = "GONG_ACCESS_KEY"
    secret_env: str = "GONG_ACCESS_SECRET"  # noqa: S105
    since: datetime = datetime(2024, 1, 1, tzinfo=UTC)
    max_pages: int = Field(default=20, ge=1)


class GongError(RuntimeError):
    pass


def _env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise GongError(f"{name} is not set")
    return value


def _list(value: JsonValue) -> list[JsonValue]:
    return value if isinstance(value, list) else []


def _customer_text(transcript: JsonValue, speakers: set[str]) -> str:
    return " ".join(
        text
        for mono in _list(lookup(transcript, "transcript"))
        if as_text(lookup(mono, "speakerId")) in speakers
        for sentence in _list(lookup(mono, "sentences"))
        if (text := as_text(lookup(sentence, "text")))
    )


class GongSource:
    name: ClassVar[str] = "gong"

    def __init__(self, config: GongConfig, ctx: Context) -> None:
        self.config = config
        self.ctx = ctx

    def _post(self, path: str, body: dict[str, JsonValue], auth: httpx.Auth) -> JsonValue:
        response = self.ctx.http.post(f"{self.config.base_url}{path}", json=body, auth=auth)
        if response.is_error:
            raise GongError(f"Gong {path} returned {response.status_code}")
        payload: JsonValue = response.json()
        return payload

    def _pages(
        self, path: str, body: dict[str, JsonValue], key: str, auth: httpx.Auth
    ) -> Iterator[JsonValue]:
        for _ in range(self.config.max_pages):
            page = self._post(path, body, auth)
            items = lookup(page, key)
            if isinstance(items, list):
                yield from items
            cursor = as_text(lookup(page, "records.cursor"))
            if cursor is None:
                return
            body = {**body, "cursor": cursor}

    def fetch(self, cursor: Cursor | None) -> Iterator[tuple[Record, Cursor]]:
        c = self.config
        auth = httpx.BasicAuth(_env(c.access_key_env), _env(c.secret_env))
        seen = cursor.get("since") if cursor else None
        since = seen if isinstance(seen, str) else c.since.isoformat()
        selector: dict[str, JsonValue] = {"exposedFields": {"parties": True}}
        calls = list(
            self._pages(
                "/v2/calls/extensive",
                {"filter": {"fromDateTime": since}, "contentSelector": selector},
                "calls",
                auth,
            )
        )
        external: dict[str, set[str]] = {}
        meta: dict[str, JsonValue] = {}
        for call in calls:
            call_id = as_text(lookup(call, "metaData.id"))
            if call_id is None:
                continue
            meta[call_id] = call
            parties = lookup(call, "parties")
            external[call_id] = {
                sid
                for p in _list(parties)
                if as_text(lookup(p, "affiliation")) == "External"
                and (sid := as_text(lookup(p, "speakerId"))) is not None
            }
        if not meta:
            return
        transcripts = self._pages(
            "/v2/calls/transcript", {"filter": {"callIds": list(meta)}}, "callTranscripts", auth
        )
        records: list[Record] = []
        for transcript in transcripts:
            call_id = as_text(lookup(transcript, "callId")) or ""
            if call_id not in meta:
                continue
            speakers = external[call_id]
            text = _customer_text(transcript, speakers)
            started = parse_time(lookup(meta[call_id], "metaData.started"))
            if not text or started is None:
                continue
            records.append(
                Record(
                    source=SourceRef(
                        type=self.name,
                        instance=c.base_url,
                        native_id=call_id,
                        url=as_text(lookup(meta[call_id], "metaData.url")),
                    ),
                    text=text,
                    created_at=started,
                    lang=as_text(lookup(meta[call_id], "metaData.language")),
                    context={"title": as_text(lookup(meta[call_id], "metaData.title")) or ""},
                )
            )
        records.sort(key=stamp)
        for i, record in enumerate(records):
            yield (
                record,
                ({"since": stamp(record)} if i == len(records) - 1 else dict(cursor or {})),
            )
