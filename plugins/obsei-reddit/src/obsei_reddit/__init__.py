"""Reddit through public RSS feeds, built on obsei's RSS source."""

from __future__ import annotations

from collections.abc import Iterator
from typing import ClassVar, Literal
from urllib.parse import urlencode

from pydantic import BaseModel, ConfigDict, Field, model_validator

from obsei.core.context import Context
from obsei.core.plugin import factory
from obsei.core.protocols import Cursor
from obsei.core.record import Record
from obsei.core.registry import Registry
from obsei.sources.rss import RssConfig, RssSource

BASE = "https://www.reddit.com"


class RedditConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    subreddit: str = Field(pattern=r"^[A-Za-z0-9_]{2,21}$")
    kind: Literal["new", "comments", "search"] = "new"
    query: str | None = None

    @model_validator(mode="after")
    def _query(self) -> RedditConfig:
        if (self.kind == "search") != (self.query is not None):
            raise ValueError("query is required for kind 'search' and only allowed with it")
        return self

    def feed_url(self) -> str:
        root = f"{BASE}/r/{self.subreddit}"
        if self.kind == "search":
            params = urlencode({"q": self.query or "", "restrict_sr": "1", "sort": "new"})
            return f"{root}/search.rss?{params}"
        return f"{root}/{self.kind}/.rss"


class RedditSource:
    name: ClassVar[str] = "reddit"

    def __init__(self, config: RedditConfig, ctx: Context) -> None:
        self.feed = RssSource(RssConfig(url=config.feed_url(), instance=config.subreddit), ctx)

    def fetch(self, cursor: Cursor | None) -> Iterator[tuple[Record, Cursor]]:
        for record, state in self.feed.fetch(cursor):
            source = record.source.model_copy(update={"type": self.name})
            yield record.model_copy(update={"source": source, "id": Record.make_id(source)}), state


def register(registry: Registry) -> None:
    registry.add_source("reddit", factory(RedditConfig, RedditSource))
