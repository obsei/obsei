"""Declarative REST source for any JSON API: helpdesks, survey tools, internal services."""

from __future__ import annotations

import os
from collections.abc import Iterator
from datetime import UTC, datetime
from typing import ClassVar, Literal

import httpx
from pydantic import BaseModel, ConfigDict, Field, JsonValue

from obsei.core.context import Context
from obsei.core.protocols import Cursor
from obsei.core.record import Record
from obsei.sources._common import FieldMap, as_text, lookup, map_item

Pagination = Literal["none", "page", "offset", "link", "next_url", "cursor"]


class RestConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    url: str
    instance: str = "default"
    method: Literal["GET", "POST"] = "GET"
    params: dict[str, str | int] = Field(default_factory=dict)
    body: dict[str, JsonValue] | None = None
    headers: dict[str, str] = Field(default_factory=dict)
    secret_headers: dict[str, str] = Field(
        default_factory=dict, description="Header name to environment variable holding its value."
    )
    bearer_token_env: str | None = None
    items_path: str | None = None
    fields: FieldMap = Field(default_factory=FieldMap)
    pagination: Pagination = "none"
    page_param: str = "page"
    page_start: int = 1
    page_size_param: str | None = None
    page_size: int = 100
    next_path: str | None = Field(
        default=None, description="Path to the next URL (next_url) or token (cursor)."
    )
    cursor_param: str = "cursor"
    since_param: str | None = Field(
        default=None, description="Query parameter that receives the newest timestamp seen."
    )
    max_pages: int = Field(default=50, ge=1)


class RestError(RuntimeError):
    pass


def _env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RestError(f"{name} is not set")
    return value


class RestSource:
    name: ClassVar[str] = "rest"

    def __init__(self, config: RestConfig, ctx: Context) -> None:
        self.config = config
        self.ctx = ctx

    def _headers(self) -> dict[str, str]:
        headers = dict(self.config.headers)
        headers.update({h: _env(env) for h, env in self.config.secret_headers.items()})
        if self.config.bearer_token_env:
            headers["Authorization"] = f"Bearer {_env(self.config.bearer_token_env)}"
        return headers

    def _request(self, url: str, params: dict[str, str | int]) -> httpx.Response:
        response = self.ctx.http.request(
            self.config.method,
            url,
            params=params or None,
            json=self.config.body,
            headers=self._headers(),
        )
        if response.is_error:
            raise RestError(f"{self.config.method} {url} returned {response.status_code}")
        return response

    def _items(self, payload: JsonValue) -> list[JsonValue]:
        items = lookup(payload, self.config.items_path) if self.config.items_path else payload
        if not isinstance(items, list):
            raise RestError(f"expected a list at {self.config.items_path or 'the top level'}")
        return items

    def _pages(self, since: str | None) -> Iterator[list[JsonValue]]:
        c = self.config
        params: dict[str, str | int] = dict(c.params)
        if c.since_param and since:
            params[c.since_param] = since
        if c.page_size_param:
            params[c.page_size_param] = c.page_size
        url: str | None = c.url
        page = c.page_start
        for _ in range(c.max_pages):
            if url is None:
                return
            if c.pagination == "page":
                params[c.page_param] = page
            elif c.pagination == "offset":
                params[c.page_param] = (page - c.page_start) * c.page_size
            response = self._request(url, params)
            payload: JsonValue = response.json()
            items = self._items(payload)
            yield items
            if not items or c.pagination == "none":
                return
            page += 1
            if c.pagination == "link":
                url = response.links.get("next", {}).get("url")
                params = {}
            elif c.pagination == "next_url":
                url = as_text(lookup(payload, c.next_path or "next"))
                params = {}
            elif c.pagination == "cursor":
                token = as_text(lookup(payload, c.next_path or "next_cursor"))
                if token is None:
                    return
                params[c.cursor_param] = token

    def fetch(self, cursor: Cursor | None) -> Iterator[tuple[Record, Cursor]]:
        since = cursor.get("since") if cursor else None
        newest = since if isinstance(since, str) else None
        now = datetime.now(UTC)
        for items in self._pages(newest):
            for item in items:
                record = map_item(
                    item,
                    self.config.fields,
                    source_type=self.name,
                    instance=self.config.instance,
                    ctx=self.ctx,
                    default_time=now,
                )
                if record is None:
                    continue
                stamp = record.created_at.astimezone(UTC).isoformat()
                newest = max(newest, stamp) if newest else stamp
                yield record, {"since": newest}
