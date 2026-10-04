"""YouTube comments on videos or a whole channel, via the YouTube Data API v3 (your API key)."""

from __future__ import annotations

import os
from collections.abc import Iterator
from typing import ClassVar

from pydantic import BaseModel, ConfigDict, Field, JsonValue, model_validator

from obsei.core.context import Context
from obsei.core.protocols import Cursor
from obsei.core.record import Record, SourceRef
from obsei.sources._common import as_float, as_text, lookup, oldest_first, parse_time, stamp

API_URL = "https://www.googleapis.com/youtube/v3/commentThreads"


class YouTubeConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    api_key_env: str = "YOUTUBE_API_KEY"
    video_ids: list[str] = Field(default_factory=list)
    channel_id: str | None = None
    max_pages: int = Field(default=5, ge=1, le=100)

    @model_validator(mode="after")
    def _target(self) -> YouTubeConfig:
        if not self.video_ids and not self.channel_id:
            raise ValueError("set video_ids or channel_id")
        return self


class YouTubeError(RuntimeError):
    pass


class YouTubeSource:
    name: ClassVar[str] = "youtube"

    def __init__(self, config: YouTubeConfig, ctx: Context) -> None:
        self.config = config
        self.ctx = ctx
        key = os.environ.get(config.api_key_env)
        if not key:
            raise YouTubeError(f"{config.api_key_env} is not set")
        self.key = key

    def _threads(self, target: tuple[str, str]) -> Iterator[JsonValue]:
        params: dict[str, str | int] = {
            "part": "snippet",
            "order": "time",
            "textFormat": "plainText",
            "maxResults": 100,
            "key": self.key,
            target[0]: target[1],
        }
        for _ in range(self.config.max_pages):
            response = self.ctx.http.get(API_URL, params=params)
            if response.is_error:
                raise YouTubeError(f"YouTube API returned {response.status_code}")
            payload: JsonValue = response.json()
            items = lookup(payload, "items")
            if isinstance(items, list):
                yield from items
            token = as_text(lookup(payload, "nextPageToken"))
            if token is None:
                return
            params["pageToken"] = token

    def _record(self, thread: JsonValue, instance: str) -> Record | None:
        comment = lookup(thread, "snippet.topLevelComment")
        comment_id = as_text(lookup(comment, "id"))
        text = as_text(lookup(comment, "snippet.textOriginal")) or as_text(
            lookup(comment, "snippet.textDisplay")
        )
        created = parse_time(lookup(comment, "snippet.publishedAt"))
        if not comment_id or not text or created is None:
            return None
        video = as_text(lookup(comment, "snippet.videoId")) or ""
        context = {"video_id": video}
        likes = as_float(lookup(comment, "snippet.likeCount"))
        if likes:
            context["likes"] = f"{likes:g}"
        return Record(
            source=SourceRef(
                type=self.name,
                instance=instance,
                native_id=comment_id,
                url=f"https://www.youtube.com/watch?v={video}&lc={comment_id}" if video else None,
            ),
            text=text,
            created_at=created,
            author=self.ctx.author(as_text(lookup(comment, "snippet.authorChannelId.value"))),
            context=context,
        )

    def fetch(self, cursor: Cursor | None) -> Iterator[tuple[Record, Cursor]]:
        state: Cursor = dict(cursor or {})
        targets = [("videoId", v) for v in self.config.video_ids]
        if self.config.channel_id:
            targets.append(("allThreadsRelatedToChannelId", self.config.channel_id))
        for target in targets:
            seen = state.get(target[1])
            fresh: list[Record] = []
            for thread in self._threads(target):
                record = self._record(thread, target[1])
                if record is None:
                    continue
                if isinstance(seen, str) and stamp(record) <= seen:
                    break
                fresh.append(record)
            yield from oldest_first(fresh, state, target[1])
