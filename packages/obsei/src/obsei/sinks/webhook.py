"""POST batches as JSON to any HTTP endpoint, optionally signed with HMAC-SHA256."""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from collections.abc import Sequence
from typing import ClassVar

from pydantic import BaseModel, ConfigDict, Field

from obsei.core.context import EGRESS, Context
from obsei.core.protocols import SinkResult
from obsei.core.record import Record
from obsei.sinks._common import env

SIGNATURE_HEADER = "X-Obsei-Signature-256"
TIMESTAMP_HEADER = "X-Obsei-Timestamp"


class WebhookConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    url: str
    secret_env: str | None = None
    headers: dict[str, str] = Field(default_factory=dict)
    exclude: list[str] = Field(default_factory=lambda: ["author"])


class WebhookSink:
    name: ClassVar[str] = "webhook"

    def __init__(self, config: WebhookConfig, ctx: Context) -> None:
        ctx.egress.check(config.url)
        self.config = config
        self.ctx = ctx
        self.secret = env(config.secret_env).encode() if config.secret_env else None

    def send(self, batch: Sequence[Record]) -> SinkResult:
        exclude = set(self.config.exclude)
        body = json.dumps(
            {"records": [r.model_dump(mode="json", exclude=exclude) for r in batch]},
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode()
        headers = {"Content-Type": "application/json", **self.config.headers}
        if self.secret:
            stamp = str(int(time.time()))
            digest = hmac.new(self.secret, stamp.encode() + b"." + body, hashlib.sha256).hexdigest()
            headers[TIMESTAMP_HEADER] = stamp
            headers[SIGNATURE_HEADER] = f"sha256={digest}"
        response = self.ctx.http.post(
            self.config.url, content=body, headers=headers, extensions=EGRESS
        )
        if response.is_error:
            return SinkResult(errors=[f"webhook returned {response.status_code}"])
        return SinkResult(sent=len(batch))
