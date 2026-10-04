"""RSS 2.0 and Atom feeds: community forums, status pages, review aggregators, subreddits."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from typing import ClassVar
from xml.etree.ElementTree import Element

from defusedxml import ElementTree
from pydantic import BaseModel, ConfigDict

from obsei.core.context import Context
from obsei.core.protocols import Cursor
from obsei.core.record import Record, SourceRef
from obsei.sources._common import html_to_text, oldest_first, parse_time, stamp

ATOM = "{http://www.w3.org/2005/Atom}"
CONTENT = "{http://purl.org/rss/1.0/modules/content/}encoded"
DC = "{http://purl.org/dc/elements/1.1/}"


class RssConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    url: str
    instance: str | None = None
    include_title: bool = True


def _text(element: Element | None) -> str:
    return (element.text or "").strip() if element is not None else ""


def _first(element: Element, *tags: str) -> str:
    for tag in tags:
        if value := _text(element.find(tag)):
            return value
    return ""


class RssSource:
    name: ClassVar[str] = "rss"

    def __init__(self, config: RssConfig, ctx: Context) -> None:
        self.config = config
        self.ctx = ctx
        self.instance = config.instance or config.url

    def _rss_item(self, item: Element) -> tuple[str, str, str, str, str, str]:
        link = _text(item.find("link"))
        return (
            _first(item, "guid") or link,
            _text(item.find("title")),
            _first(item, CONTENT, "description"),
            _first(item, "pubDate", f"{DC}date"),
            link,
            _first(item, f"{DC}creator", "author"),
        )

    def _atom_entry(self, entry: Element) -> tuple[str, str, str, str, str, str]:
        link = entry.find(f"{ATOM}link[@rel='alternate']")
        if link is None:
            link = entry.find(f"{ATOM}link")
        return (
            _text(entry.find(f"{ATOM}id")),
            _text(entry.find(f"{ATOM}title")),
            _first(entry, f"{ATOM}content", f"{ATOM}summary"),
            _first(entry, f"{ATOM}updated", f"{ATOM}published"),
            link.get("href", "") if link is not None else "",
            _text(entry.find(f"{ATOM}author/{ATOM}name")),
        )

    def _records(self, root: Element) -> Iterator[Record]:
        if root.tag == f"{ATOM}feed":
            rows = [self._atom_entry(e) for e in root.findall(f"{ATOM}entry")]
        else:
            rows = [self._rss_item(i) for i in root.iter("item")]
        now = datetime.now(UTC)
        for native_id, title, body, when, link, author in rows:
            parts = [title] if self.config.include_title and title else []
            if text := html_to_text(body):
                parts.append(text)
            if not native_id or not parts:
                continue
            yield Record(
                source=SourceRef(
                    type=self.name, instance=self.instance, native_id=native_id, url=link or None
                ),
                text="\n\n".join(parts),
                created_at=parse_time(when) or now,
                author=self.ctx.author(author),
            )

    def fetch(self, cursor: Cursor | None) -> Iterator[tuple[Record, Cursor]]:
        response = self.ctx.http.get(self.config.url)
        response.raise_for_status()
        root: Element = ElementTree.fromstring(response.content)
        state: Cursor = dict(cursor or {})
        seen = state.get("since")
        fresh = [r for r in self._records(root) if not (isinstance(seen, str) and stamp(r) <= seen)]
        yield from oldest_first(fresh, state, "since")
