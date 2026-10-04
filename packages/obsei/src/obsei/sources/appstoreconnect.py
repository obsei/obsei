"""App Store Connect customer reviews for your own apps, in every territory (official API).

Needs an API key (.p8) and ``pip install 'obsei[apple]'``.
"""

from __future__ import annotations

import os
import time
from collections.abc import Iterator
from pathlib import Path
from typing import ClassVar

from pydantic import BaseModel, ConfigDict, Field, JsonValue, model_validator

from obsei.core.context import Context
from obsei.core.protocols import Cursor
from obsei.core.record import Record, SourceRef
from obsei.sources._common import as_float, as_text, lookup, oldest_first, parse_time, stamp

API_URL = "https://api.appstoreconnect.apple.com/v1/apps/{app_id}/customerReviews"
TOKEN_TTL = 15 * 60


class AppStoreConnectConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    app_id: str = Field(pattern=r"^\d+$")
    issuer_id_env: str = "ASC_ISSUER_ID"
    key_id_env: str = "ASC_KEY_ID"
    private_key_file: Path | None = None
    private_key_env: str | None = None
    territories: list[str] = Field(
        default_factory=list, description="ISO 3166 alpha-3 codes, e.g. USA, DEU, JPN, BRA, IND."
    )
    max_pages: int = Field(default=20, ge=1)

    @model_validator(mode="after")
    def _one_key(self) -> AppStoreConnectConfig:
        if (self.private_key_file is None) == (self.private_key_env is None):
            raise ValueError("set exactly one of private_key_file or private_key_env")
        return self


class AppStoreConnectError(RuntimeError):
    pass


def _env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise AppStoreConnectError(f"{name} is not set")
    return value


class AppStoreConnectSource:
    name: ClassVar[str] = "appstoreconnect"

    def __init__(self, config: AppStoreConnectConfig, ctx: Context) -> None:
        self.config = config
        self.ctx = ctx

    def _token(self) -> str:
        try:
            import jwt  # noqa: PLC0415
        except ImportError:
            raise AppStoreConnectError("needs: pip install 'obsei[apple]'") from None
        c = self.config
        key = (
            c.private_key_file.read_text(encoding="utf-8")
            if c.private_key_file
            else _env(c.private_key_env or "")
        )
        now = int(time.time())
        return jwt.encode(
            {
                "iss": _env(c.issuer_id_env),
                "iat": now,
                "exp": now + TOKEN_TTL,
                "aud": "appstoreconnect-v1",
            },
            key,
            algorithm="ES256",
            headers={"kid": _env(c.key_id_env), "typ": "JWT"},
        )

    def _reviews(self) -> Iterator[JsonValue]:
        headers = {"Authorization": f"Bearer {self._token()}"}
        params: dict[str, str | int] | None = {"sort": "-createdDate", "limit": 200}
        if params is not None and self.config.territories:
            params["filter[territory]"] = ",".join(self.config.territories)
        url: str | None = API_URL.format(app_id=self.config.app_id)
        for _ in range(self.config.max_pages):
            if url is None:
                return
            response = self.ctx.http.get(url, params=params, headers=headers)
            if response.is_error:
                raise AppStoreConnectError(f"App Store Connect returned {response.status_code}")
            payload: JsonValue = response.json()
            data = lookup(payload, "data")
            if isinstance(data, list):
                yield from data
            url = as_text(lookup(payload, "links.next"))
            params = None

    def _record(self, review: JsonValue) -> Record | None:
        review_id = as_text(lookup(review, "id"))
        body = as_text(lookup(review, "attributes.body"))
        created = parse_time(lookup(review, "attributes.createdDate"))
        if not review_id or not body or created is None:
            return None
        title = as_text(lookup(review, "attributes.title"))
        context = {"territory": as_text(lookup(review, "attributes.territory")) or ""}
        if title:
            context["title"] = title
        return Record(
            source=SourceRef(type=self.name, instance=self.config.app_id, native_id=review_id),
            text=f"{title}\n\n{body}" if title else body,
            created_at=created,
            author=self.ctx.author(as_text(lookup(review, "attributes.reviewerNickname"))),
            rating=as_float(lookup(review, "attributes.rating")),
            context=context,
        )

    def fetch(self, cursor: Cursor | None) -> Iterator[tuple[Record, Cursor]]:
        state: Cursor = dict(cursor or {})
        seen = state.get("since")
        fresh: list[Record] = []
        for review in self._reviews():
            record = self._record(review)
            if record is None:
                continue
            if isinstance(seen, str) and stamp(record) <= seen:
                break
            fresh.append(record)
        yield from oldest_first(fresh, state, "since")
