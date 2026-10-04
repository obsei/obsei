"""Hacker News stories and comments matching a query, via the public Algolia search API."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from typing import ClassVar, Literal, TypeAlias

from pydantic import BaseModel, ConfigDict, Field, JsonValue

from obsei.core.context import Context
from obsei.core.protocols import Cursor
from obsei.core.record import Record, SourceRef
from obsei.sources._common import as_float, as_text, html_to_text, lookup, oldest_first, stamp

API_URL = "https://hn.algolia.com/api/v1/search_by_date"
Kind: TypeAlias = Literal["story", "comment"]
ALL_KINDS: list[Kind] = ["story", "comment"]


class HackerNewsConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str = Field(min_length=1)
    kinds: list[Kind] = Field(default_factory=lambda: list(ALL_KINDS))
    max_pages: int = Field(default=5, ge=1, le=50)


class HackerNewsSource:
    name: ClassVar[str] = "hackernews"

    def __init__(self, config: HackerNewsConfig, ctx: Context) -> None:
        self.config = config
        self.ctx = ctx

    def _hits(self, since: int) -> Iterator[JsonValue]:
        tags = ",".join(self.config.kinds)
        for page in range(self.config.max_pages):
            response = self.ctx.http.get(
                API_URL,
                params={
                    "query": self.config.query,
                    "tags": f"({tags})",
                    "numericFilters": f"created_at_i>{since}",
                    "hitsPerPage": 100,
                    "page": page,
                },
            )
            response.raise_for_status()
            payload: JsonValue = response.json()
            hits = lookup(payload, "hits")
            if not isinstance(hits, list) or not hits:
                return
            yield from hits
            pages = as_float(lookup(payload, "nbPages")) or 0
            if page + 1 >= pages:
                return

    def _record(self, hit: JsonValue) -> Record | None:
        object_id = as_text(lookup(hit, "objectID"))
        seconds = as_float(lookup(hit, "created_at_i"))
        body = as_text(lookup(hit, "comment_text")) or as_text(lookup(hit, "story_text")) or ""
        title = as_text(lookup(hit, "title")) or ""
        text = "\n\n".join(p for p in (title, html_to_text(body)) if p)
        if not object_id or seconds is None or not text:
            return None
        story = as_text(lookup(hit, "story_id"))
        context = {"kind": "comment" if lookup(hit, "comment_text") else "story"}
        if story and story != object_id:
            context["story_id"] = story
        return Record(
            source=SourceRef(
                type=self.name,
                instance=self.config.query,
                native_id=object_id,
                url=f"https://news.ycombinator.com/item?id={object_id}",
            ),
            text=text,
            created_at=datetime.fromtimestamp(seconds, UTC),
            author=self.ctx.author(as_text(lookup(hit, "author"))),
            lang=None,
            context=context,
        )

    def fetch(self, cursor: Cursor | None) -> Iterator[tuple[Record, Cursor]]:
        state: Cursor = dict(cursor or {})
        seen = state.get("since")
        since = int(datetime.fromisoformat(seen).timestamp()) if isinstance(seen, str) else 0
        fresh = [
            r
            for hit in self._hits(since)
            if (r := self._record(hit)) is not None
            and not (isinstance(seen, str) and stamp(r) <= seen)
        ]
        yield from oldest_first(fresh, state, "since")
