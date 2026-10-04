"""Google Play reviews through the official Android Publisher API (your own apps).

The API returns reviews created or edited in the last week, so schedule at least weekly.
Authenticate with a service-account file (``pip install 'obsei[google]'``) or a token env var.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import ClassVar

from pydantic import BaseModel, ConfigDict, Field, JsonValue, model_validator

from obsei.core.context import Context
from obsei.core.protocols import Cursor
from obsei.core.record import Record, SourceRef
from obsei.sources._common import as_float, as_text, lookup, oldest_first, stamp

API_URL = (
    "https://androidpublisher.googleapis.com/androidpublisher/v3/applications/{package}/reviews"
)
SCOPE = "https://www.googleapis.com/auth/androidpublisher"


class PlayStoreConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    package_name: str = Field(pattern=r"^[A-Za-z][\w]*(\.[A-Za-z][\w]*)+$")
    credentials_file: Path | None = None
    access_token_env: str | None = None
    translation_language: str | None = None
    max_pages: int = Field(default=100, ge=1)

    @model_validator(mode="after")
    def _one_auth(self) -> PlayStoreConfig:
        if (self.credentials_file is None) == (self.access_token_env is None):
            raise ValueError("set exactly one of credentials_file or access_token_env")
        return self


class PlayStoreError(RuntimeError):
    pass


def _service_account_token(path: Path) -> str:
    try:
        from google.auth.transport.requests import Request  # noqa: PLC0415
        from google.oauth2 import service_account  # noqa: PLC0415
    except ImportError:
        raise PlayStoreError("credentials_file needs: pip install 'obsei[google]'") from None
    credentials = service_account.Credentials.from_service_account_file(  # type: ignore[no-untyped-call]
        str(path), scopes=[SCOPE]
    )
    credentials.refresh(Request())
    token: str | None = credentials.token
    if not token:
        raise PlayStoreError("service account did not return an access token")
    return token


def _seconds(value: JsonValue) -> datetime | None:
    seconds = as_float(lookup(value, "seconds"))
    return None if seconds is None else datetime.fromtimestamp(seconds, UTC)


class PlayStoreSource:
    name: ClassVar[str] = "playstore"

    def __init__(self, config: PlayStoreConfig, ctx: Context) -> None:
        self.config = config
        self.ctx = ctx

    def _token(self) -> str:
        if self.config.credentials_file is not None:
            return _service_account_token(self.config.credentials_file)
        env = self.config.access_token_env or ""
        token = os.environ.get(env)
        if not token:
            raise PlayStoreError(f"{env} is not set")
        return token

    def _reviews(self) -> Iterator[JsonValue]:
        headers = {"Authorization": f"Bearer {self._token()}"}
        params: dict[str, str | int] = {"maxResults": 100}
        if self.config.translation_language:
            params["translationLanguage"] = self.config.translation_language
        url = API_URL.format(package=self.config.package_name)
        for _ in range(self.config.max_pages):
            response = self.ctx.http.get(url, params=params, headers=headers)
            if response.is_error:
                raise PlayStoreError(f"Play API returned {response.status_code}")
            payload: JsonValue = response.json()
            reviews = lookup(payload, "reviews")
            if isinstance(reviews, list):
                yield from reviews
            token = as_text(lookup(payload, "tokenPagination.nextPageToken"))
            if token is None:
                return
            params["token"] = token

    def _record(self, review: JsonValue) -> Record | None:
        review_id = as_text(lookup(review, "reviewId"))
        comment = lookup(review, "comments.0.userComment")
        text = as_text(lookup(comment, "text"))
        created = _seconds(lookup(comment, "lastModified"))
        if not review_id or not text or created is None:
            return None
        lang = as_text(lookup(comment, "reviewerLanguage"))
        context = {
            key: value
            for key, path in (
                ("app_version", "appVersionName"),
                ("device", "device"),
                ("android_os", "androidOsVersion"),
                ("original_text", "originalText"),
            )
            if (value := as_text(lookup(comment, path))) is not None
        }
        if reply := as_text(lookup(review, "comments.1.developerComment.text")):
            context["developer_reply"] = reply
        return Record(
            source=SourceRef(
                type=self.name, instance=self.config.package_name, native_id=review_id
            ),
            text=text,
            created_at=created,
            author=self.ctx.author(as_text(lookup(review, "authorName")), lang),
            rating=as_float(lookup(comment, "starRating")),
            lang=lang,
            context=context,
        )

    def fetch(self, cursor: Cursor | None) -> Iterator[tuple[Record, Cursor]]:
        state: Cursor = dict(cursor or {})
        seen = state.get("since")
        fresh = [
            record
            for review in self._reviews()
            if (record := self._record(review)) is not None
            and not (isinstance(seen, str) and stamp(record) <= seen)
        ]
        yield from oldest_first(fresh, state, "since")
