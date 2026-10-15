"""Apple App Store public customer-reviews feed (latest ~500 reviews per country, no key)."""

from __future__ import annotations

from collections.abc import Iterator
from typing import ClassVar
from xml.etree.ElementTree import Element

from defusedxml import ElementTree
from pydantic import BaseModel, ConfigDict, Field

from obsei.core.context import Context
from obsei.core.protocols import Cursor
from obsei.core.record import Record, SourceRef
from obsei.sources._common import as_float, oldest_first, parse_time, stamp

# The XML feed: Apple's JSON variant of the same URL intermittently returns no entries.
FEED_URL = "https://itunes.apple.com/{country}/rss/customerreviews/page={page}/id={app_id}/sortby=mostrecent/xml"
NS = {"a": "http://www.w3.org/2005/Atom", "im": "http://itunes.apple.com/rss"}
MAX_PAGES = 10


class AppStoreConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    app_id: str = Field(
        pattern=r"^\d+$", description="The digits after 'id' in the app's App Store link."
    )
    countries: list[str] = Field(
        default_factory=lambda: ["us"],
        min_length=1,
        description="Storefronts as ISO 3166 alpha-2 codes, e.g. us, gb, de, jp.",
    )
    max_pages: int = Field(
        default=MAX_PAGES,
        ge=1,
        le=MAX_PAGES,
        description="Feed pages per country, 50 reviews each.",
    )


def _text(entry: Element, path: str) -> str | None:
    node = entry.find(path, NS)
    text = node.text.strip() if node is not None and node.text else ""
    return text or None


class AppStoreSource:
    name: ClassVar[str] = "appstore"

    def __init__(self, config: AppStoreConfig, ctx: Context) -> None:
        self.config = config
        self.ctx = ctx

    def _entries(self, country: str) -> Iterator[Element]:
        for page in range(1, self.config.max_pages + 1):
            url = FEED_URL.format(country=country, page=page, app_id=self.config.app_id)
            response = self.ctx.http.get(url)
            if response.status_code in (400, 404):
                return
            response.raise_for_status()
            entries = ElementTree.fromstring(response.content).findall("a:entry", NS)
            if not entries:
                return
            yield from entries

    def _record(self, entry: Element, country: str) -> Record | None:
        review_id, rating = _text(entry, "a:id"), _text(entry, "im:rating")
        created = parse_time(_text(entry, "a:updated"))
        body = _text(entry, "a:content[@type='text']")
        if not review_id or rating is None or created is None or not body:
            return None
        title = _text(entry, "a:title")
        context = {"country": country}
        if version := _text(entry, "im:version"):
            context["app_version"] = version
        if title:
            context["title"] = title
        link = entry.find("a:link", NS)
        return Record(
            source=SourceRef(
                type=self.name,
                instance=self.config.app_id,
                native_id=review_id,
                url=link.get("href") if link is not None else None,
            ),
            text=f"{title}\n\n{body}" if title else body,
            created_at=created,
            author=self.ctx.author(_text(entry, "a:author/a:name"), None),
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
