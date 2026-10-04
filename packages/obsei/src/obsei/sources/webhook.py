"""Push intake for ``obsei serve``: POST /ingest/{pipeline}/{source}, HMAC-SHA256 signed.

Map ``fields.id`` and ``fields.created_at`` so redeliveries are recognised as unchanged;
without a timestamp the receipt time is used and a redelivery counts as an edit.

Senders sign ``{X-Obsei-Timestamp}.{body}``; requests more than ``max_age_seconds`` old are
refused, so a captured request cannot be replayed later. Body-only signatures (GitHub style) are
accepted only with ``require_timestamp: false``. Each request is parsed in full before anything is
stored: one bad item rejects the whole request, and items without text are skipped.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import time
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import ClassVar

from pydantic import BaseModel, ConfigDict, Field, JsonValue, ValidationError, model_validator

from obsei.core.context import Context
from obsei.core.protocols import Cursor
from obsei.core.record import Record
from obsei.sources._common import FieldMap, lookup, map_item

SIGNATURE_HEADERS = ("x-obsei-signature-256", "x-hub-signature-256")
TIMESTAMP_HEADER = "x-obsei-timestamp"


class WebhookSourceConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    secret_env: str | None = None
    allow_unsigned: bool = False
    require_timestamp: bool = True
    max_age_seconds: int = Field(default=300, ge=1)
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


class PayloadError(ValueError):
    pass


@dataclass(frozen=True)
class Delivery:
    """The records of one request; a ``Source`` that yields them once."""

    name: ClassVar[str] = "webhook"
    records: Sequence[Record]
    received: int
    skipped: int

    def fetch(self, cursor: Cursor | None) -> Iterator[tuple[Record, Cursor]]:
        for record in self.records:
            yield record, dict(cursor or {})


class WebhookSource:
    name: ClassVar[str] = "webhook"

    def __init__(self, config: WebhookSourceConfig, ctx: Context) -> None:
        self.config = config
        self.ctx = ctx
        self.secret = os.environ.get(config.secret_env, "").encode() if config.secret_env else b""
        if config.secret_env and not self.secret:
            raise SignatureError(f"{config.secret_env} is not set")
        self.pending: list[Record] = []

    def verify(self, body: bytes, headers: dict[str, str], now: float | None = None) -> None:
        if not self.secret:
            return
        stamp = headers.get(TIMESTAMP_HEADER, "")
        if stamp:
            try:
                sent = int(stamp)
            except ValueError:
                raise SignatureError("invalid X-Obsei-Timestamp") from None
            if abs((now or time.time()) - sent) > self.config.max_age_seconds:
                raise SignatureError("stale request: X-Obsei-Timestamp is outside the window")
            signed = stamp.encode() + b"." + body
        elif self.config.require_timestamp:
            raise SignatureError("missing X-Obsei-Timestamp")
        else:
            signed = body
        expected = "sha256=" + hmac.new(self.secret, signed, hashlib.sha256).hexdigest()
        given = next((headers[h] for h in SIGNATURE_HEADERS if h in headers), "")
        if not hmac.compare_digest(expected.encode(), given.encode()):
            raise SignatureError("invalid or missing signature")

    def parse(self, payload: JsonValue) -> Delivery:
        """Map every item of one request, or raise ``PayloadError`` without keeping any."""
        items = lookup(payload, self.config.items_path) if self.config.items_path else payload
        rows = items if isinstance(items, list) else [items]
        now = datetime.now(UTC)
        records: list[Record] = []
        for index, row in enumerate(rows):
            try:
                record = map_item(
                    row,
                    self.config.fields,
                    source_type=self.name,
                    instance=self.config.instance,
                    ctx=self.ctx,
                    default_time=now,
                )
            except ValidationError as exc:
                fields = sorted({str(e["loc"][0]) for e in exc.errors() if e["loc"]})
                raise PayloadError(
                    f"item {index} is invalid: {', '.join(fields) or 'record'}"
                ) from None
            except (ValueError, TypeError, OverflowError, OSError) as exc:
                raise PayloadError(f"item {index} is invalid: {exc}") from None
            if record is not None:
                records.append(record)
        return Delivery(records, received=len(rows), skipped=len(rows) - len(records))

    def accept(self, payload: JsonValue) -> int:
        """Queue one request's records for the next ``fetch``; all or nothing."""
        self.pending.extend(self.parse(payload).records)
        return len(self.pending)

    def fetch(self, cursor: Cursor | None) -> Iterator[tuple[Record, Cursor]]:
        pending, self.pending = self.pending, []
        for record in pending:
            yield record, dict(cursor or {})
