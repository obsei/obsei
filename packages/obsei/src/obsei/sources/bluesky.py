"""Bluesky posts matching a search query (AT Protocol). Optional app-password login."""

from __future__ import annotations

import os
from collections.abc import Iterator
from typing import ClassVar

from pydantic import BaseModel, ConfigDict, Field, JsonValue

from obsei.core.context import Context
from obsei.core.protocols import Cursor
from obsei.core.record import Record, SourceRef
from obsei.sources._common import as_text, lookup, oldest_first, parse_time, stamp

PUBLIC_API = "https://public.api.bsky.app"


class BlueskyConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str = Field(min_length=1)
    lang: str | None = Field(default=None, description="Only posts tagged with this language.")
    service: str = "https://bsky.social"
    handle_env: str | None = None
    app_password_env: str | None = None
    include_urls: bool = Field(
        default=False, description="Post URLs embed the author's DID, so they are off by default."
    )
    max_pages: int = Field(default=5, ge=1, le=50)


class BlueskyError(RuntimeError):
    pass


class BlueskySource:
    name: ClassVar[str] = "bluesky"

    def __init__(self, config: BlueskyConfig, ctx: Context) -> None:
        self.config = config
        self.ctx = ctx

    def _session(self) -> tuple[str, dict[str, str]]:
        c = self.config
        if not (c.handle_env and c.app_password_env):
            return PUBLIC_API, {}
        handle, password = os.environ.get(c.handle_env), os.environ.get(c.app_password_env)
        if not handle or not password:
            raise BlueskyError(f"{c.handle_env} and {c.app_password_env} must be set")
        response = self.ctx.http.post(
            f"{c.service}/xrpc/com.atproto.server.createSession",
            json={"identifier": handle, "password": password},
        )
        if response.is_error:
            raise BlueskyError(f"Bluesky login failed with {response.status_code}")
        token = as_text(lookup(response.json(), "accessJwt"))
        if token is None:
            raise BlueskyError("Bluesky login returned no token")
        return c.service, {"Authorization": f"Bearer {token}"}

    def _posts(self, since: str | None) -> Iterator[JsonValue]:
        base, headers = self._session()
        params: dict[str, str | int] = {"q": self.config.query, "sort": "latest", "limit": 100}
        if self.config.lang:
            params["lang"] = self.config.lang
        if since:
            params["since"] = since
        for _ in range(self.config.max_pages):
            response = self.ctx.http.get(
                f"{base}/xrpc/app.bsky.feed.searchPosts", params=params, headers=headers
            )
            if response.is_error:
                raise BlueskyError(f"Bluesky search returned {response.status_code}")
            payload: JsonValue = response.json()
            posts = lookup(payload, "posts")
            if isinstance(posts, list):
                yield from posts
            token = as_text(lookup(payload, "cursor"))
            if not token or not posts:
                return
            params["cursor"] = token

    def _record(self, post: JsonValue) -> Record | None:
        uri = as_text(lookup(post, "uri"))
        text = as_text(lookup(post, "record.text"))
        created = parse_time(lookup(post, "record.createdAt"))
        if not uri or not text or created is None:
            return None
        langs = lookup(post, "record.langs")
        lang = as_text(langs[0]) if isinstance(langs, list) and langs else None
        url = None
        if self.config.include_urls and uri.startswith("at://"):
            did, _, rkey = uri.removeprefix("at://").partition("/app.bsky.feed.post/")
            url = f"https://bsky.app/profile/{did}/post/{rkey}"
        return Record(
            source=SourceRef(type=self.name, instance=self.config.query, native_id=uri, url=url),
            text=text,
            created_at=created,
            author=self.ctx.author(as_text(lookup(post, "author.did")), lang),
            lang=lang,
        )

    def fetch(self, cursor: Cursor | None) -> Iterator[tuple[Record, Cursor]]:
        state: Cursor = dict(cursor or {})
        seen = state.get("since")
        since = seen if isinstance(seen, str) else None
        fresh = [
            r
            for post in self._posts(since)
            if (r := self._record(post)) is not None and not (since and stamp(r) <= since)
        ]
        yield from oldest_first(fresh, state, "since")
