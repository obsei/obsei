"""Apple App Store public customer-reviews feed (latest reviews per country, no key)."""

from __future__ import annotations

from collections.abc import Iterator
from typing import ClassVar, NamedTuple
from xml.etree.ElementTree import Element

import httpx
from defusedxml import ElementTree
from pydantic import BaseModel, ConfigDict, Field, JsonValue

from obsei.core.context import Context
from obsei.core.protocols import Cursor
from obsei.core.record import Record, SourceRef
from obsei.sources._common import as_float, as_text, lookup, oldest_first, parse_time, stamp

FEED_URL = "https://itunes.apple.com/{country}/rss/customerreviews/{path}/{format}"
# Apple's CDN often serves one spelling of the feed empty while another has the reviews, so
# page 1 tries each spelling, as XML then JSON, until one has entries.
FIRST_PAGE = (
    "page=1/id={app_id}/sortby=mostrecent",
    "id={app_id}/sortby=mostrecent",
    "id={app_id}/sortBy=mostRecent",
    "id={app_id}",
)
NEXT_PAGE = "page={page}/id={app_id}/sortby=mostrecent"
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


class Review(NamedTuple):
    id: str | None
    rating: str | None
    updated: str | None
    body: str | None
    title: str | None
    version: str | None
    author: str | None
    url: str | None


def _text(entry: Element, path: str) -> str | None:
    node = entry.find(path, NS)
    text = node.text.strip() if node is not None and node.text else ""
    return text or None


def _from_xml(content: bytes) -> list[Review]:
    reviews = []
    for e in ElementTree.fromstring(content).findall("a:entry", NS):
        link = e.find("a:link", NS)
        reviews.append(
            Review(
                id=_text(e, "a:id"),
                rating=_text(e, "im:rating"),
                updated=_text(e, "a:updated"),
                body=_text(e, "a:content[@type='text']"),
                title=_text(e, "a:title"),
                version=_text(e, "im:version"),
                author=_text(e, "a:author/a:name"),
                url=link.get("href") if link is not None else None,
            )
        )
    return reviews


def _from_json(data: JsonValue) -> list[Review]:
    entries = lookup(data, "feed.entry")
    if isinstance(entries, dict):
        entries = [entries]
    if not isinstance(entries, list):
        return []

    def label(e: JsonValue, path: str) -> str | None:
        return as_text(lookup(e, f"{path}.label"))

    return [
        Review(
            id=label(e, "id"),
            rating=label(e, "im:rating"),
            updated=label(e, "updated"),
            body=label(e, "content"),
            title=label(e, "title"),
            version=label(e, "im:version"),
            author=label(e, "author.name"),
            url=as_text(lookup(e, "link.attributes.href")),
        )
        for e in entries
    ]


class AppStoreSource:
    name: ClassVar[str] = "appstore"

    def __init__(self, config: AppStoreConfig, ctx: Context) -> None:
        self.config = config
        self.ctx = ctx

    def _get(self, url: str) -> httpx.Response | None:
        response = self.ctx.http.get(url)
        if response.status_code in (400, 404):
            return None
        response.raise_for_status()
        return response

    def _page(self, country: str, page: int) -> list[Review]:
        paths = FIRST_PAGE if page == 1 else (NEXT_PAGE,)
        for path in paths:
            spelled = path.format(app_id=self.config.app_id, page=page)
            for fmt in ("xml", "json"):
                url = FEED_URL.format(country=country, path=spelled, format=fmt)
                response = self._get(url)
                if response is None:
                    continue
                reviews = (
                    _from_xml(response.content) if fmt == "xml" else _from_json(response.json())
                )
                if reviews:
                    return reviews
        return []

    def _reviews(self, country: str) -> Iterator[Review]:
        for page in range(1, self.config.max_pages + 1):
            reviews = self._page(country, page)
            if not reviews:
                return
            yield from reviews

    def _record(self, review: Review, country: str) -> Record | None:
        created = parse_time(review.updated)
        if not review.id or review.rating is None or created is None or not review.body:
            return None
        context = {"country": country}
        if review.version:
            context["app_version"] = review.version
        if review.title:
            context["title"] = review.title
        return Record(
            source=SourceRef(
                type=self.name, instance=self.config.app_id, native_id=review.id, url=review.url
            ),
            text=f"{review.title}\n\n{review.body}" if review.title else review.body,
            created_at=created,
            author=self.ctx.author(review.author, None),
            rating=as_float(review.rating),
            context=context,
        )

    def fetch(self, cursor: Cursor | None) -> Iterator[tuple[Record, Cursor]]:
        state: Cursor = dict(cursor or {})
        for country in self.config.countries:
            seen = state.get(country)
            fresh: list[Record] = []
            for review in self._reviews(country):
                record = self._record(review, country)
                if record is None:
                    continue
                if isinstance(seen, str) and stamp(record) <= seen:
                    break
                fresh.append(record)
            yield from oldest_first(fresh, state, country)
