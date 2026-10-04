"""Push intake for ``obsei serve``: POST /ingest/{pipeline}/{source}, HMAC-SHA256 signed.

Map ``fields.id`` and ``fields.created_at`` so redeliveries are recognised as unchanged;
without a timestamp the receipt time is used and a redelivery counts as an edit.
"""

from __future__ import annotations

import hashlib
import hmac
import os
from collections.abc import Iterator
from datetime import UTC, datetime
from typing import ClassVar

from pydantic import BaseModel, ConfigDict, Field, JsonValue, model_validator

from obsei.core.context import Context
from obsei.core.protocols import Cursor
from obsei.core.record import Record
from obsei.sources._common import FieldMap, lookup, map_item

SIGNATURE_HEADERS = ("x-obsei-signature-256", "x-hub-signature-256")


class WebhookSourceConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    secret_env: str | None = None
    allow_unsigned: bool = False
    instance: str = "default"
    items_path: str | None = None
    fields: FieldMap = Field(default_factory=FieldMap)

    @model_validator(mode="after")
    def _signed(self) -> WebhookSourceConfig:
        if self.secret_env is None and not self.allow_unsigned:
            raise ValueError("set secret_env, or allow_unsigned: true on a trusted network")
        return self


class SignatureError(PermissionError):
    pass


class WebhookSource:
    name: ClassVar[str] = "webhook"

    def __init__(self, config: WebhookSourceConfig, ctx: Context) -> None:
        self.config = config
        self.ctx = ctx
        self.secret = os.environ.get(config.secret_env, "").encode() if config.secret_env else b""
        if config.secret_env and not self.secret:
            raise SignatureError(f"{config.secret_env} is not set")
        self.pending: list[Record] = []

    def verify(self, body: bytes, headers: dict[str, str]) -> None:
        if not self.secret:
            return
        expected = "sha256=" + hmac.new(self.secret, body, hashlib.sha256).hexdigest()
        given = next((headers[h] for h in SIGNATURE_HEADERS if h in headers), "")
        if not hmac.compare_digest(expected.encode(), given.encode()):
            raise SignatureError("invalid or missing signature")

    def accept(self, payload: JsonValue) -> int:
        items = lookup(payload, self.config.items_path) if self.config.items_path else payload
        rows = items if isinstance(items, list) else [items]
        now = datetime.now(UTC)
        for row in rows:
            record = map_item(
                row,
                self.config.fields,
                source_type=self.name,
                instance=self.config.instance,
                ctx=self.ctx,
                default_time=now,
            )
            if record is not None:
                self.pending.append(record)
        return len(self.pending)

    def fetch(self, cursor: Cursor | None) -> Iterator[tuple[Record, Cursor]]:
        pending, self.pending = self.pending, []
        for record in pending:
            yield record, dict(cursor or {})
