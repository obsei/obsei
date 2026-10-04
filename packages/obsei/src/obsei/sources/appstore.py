"""Apple App Store public customer-reviews feed (latest ~500 reviews per country, no key)."""

from __future__ import annotations

from collections.abc import Iterator
from typing import ClassVar

from pydantic import BaseModel, ConfigDict, Field, JsonValue

from obsei.core.context import Context
from obsei.core.protocols import Cursor
from obsei.core.record import Record, SourceRef
from obsei.sources._common import as_float, as_text, lookup, oldest_first, parse_time, stamp

FEED_URL = "https://itunes.apple.com/{country}/rss/customerreviews/page={page}/id={app_id}/sortby=mostrecent/json"
MAX_PAGES = 10


class AppStoreConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    app_id: str = Field(pattern=r"^\d+$")
    countries: list[str] = Field(default_factory=lambda: ["us"], min_length=1)
    max_pages: int = Field(default=MAX_PAGES, ge=1, le=MAX_PAGES)


def _label(entry: JsonValue, path: str) -> str | None:
    return as_text(lookup(entry, f"{path}.label"))


class AppStoreSource:
    name: ClassVar[str] = "appstore"

    def __init__(self, config: AppStoreConfig, ctx: Context) -> None:
        self.config = config
        self.ctx = ctx

    def _entries(self, country: str) -> Iterator[JsonValue]:
        for page in range(1, self.config.max_pages + 1):
            url = FEED_URL.format(country=country, page=page, app_id=self.config.app_id)
            response = self.ctx.http.get(url)
            if response.status_code in (400, 404):
                return
            response.raise_for_status()
            entries = lookup(response.json(), "feed.entry")
            if isinstance(entries, dict):
                entries = [entries]
            if not isinstance(entries, list) or not entries:
                return
            yield from entries

    def _record(self, entry: JsonValue, country: str) -> Record | None:
        review_id, rating = _label(entry, "id"), _label(entry, "im:rating")
        created = parse_time(_label(entry, "updated"))
        body = _label(entry, "content")
        if not review_id or rating is None or created is None or not body:
            return None
        title = _label(entry, "title")
        context = {"country": country}
        if version := _label(entry, "im:version"):
            context["app_version"] = version
        if title:
            context["title"] = title
        return Record(
            source=SourceRef(
                type=self.name,
                instance=self.config.app_id,
                native_id=review_id,
                url=as_text(lookup(entry, "link.attributes.href")),
            ),
            text=f"{title}\n\n{body}" if title else body,
            created_at=created,
            author=self.ctx.author(_label(entry, "author.name"), None),
            rating=as_float(rating),
            context=context,
        )

    def fetch(self, cursor: Cursor | None) -> Iterator[tuple[Record, Cursor]]:
        state: Cursor = dict(cursor or {})
        for country in self.config.countries:
            seen = state.get(country)
            fresh: list[Record] = []
            for entry in self._entries(country):
                record = self._record(entry, country)
                if record is None:
                    continue
                if isinstance(seen, str) and stamp(record) <= seen:
                    break
                fresh.append(record)
            yield from oldest_first(fresh, state, country)
