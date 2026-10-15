"""POST batches as CloudEvents-shaped JSON to any HTTP endpoint, optionally signed per Standard
Webhooks (https://www.standardwebhooks.com/), retried on connection errors, 429 and 5xx."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
import uuid
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import ClassVar

import httpx
from pydantic import BaseModel, ConfigDict, Field, JsonValue

from obsei.core.context import EGRESS, Context
from obsei.core.plugin import SECRET
from obsei.core.protocols import Alert, AlertKind, EventDelivery, SinkResult
from obsei.core.record import Record
from obsei.sinks._common import env

RECORDS_ROUTED = "obsei.records.routed"
ALERT_EVENTS: dict[AlertKind, str] = {
    "theme_spike": "obsei.theme.spiking",
    "new_theme": "obsei.theme.new",
    "digest": "obsei.digest",
    "review_queue": "obsei.review.pending",
    "pipeline_health": "obsei.pipeline.failed",
}
SECRET_PREFIX = "whsec_"  # noqa: S105
ATTEMPTS = 3
BACKOFF_SECONDS = 1.0
MAX_RETRY_AFTER = 30
TOO_MANY_REQUESTS = 429
SERVER_ERROR = 500


def signing_key(secret: str) -> bytes:
    """``whsec_<base64>`` secrets decode to their bytes, as in the standardwebhooks libraries;
    any other value is used as its raw UTF-8 bytes."""
    if secret.startswith(SECRET_PREFIX):
        return base64.b64decode(secret.removeprefix(SECRET_PREFIX) + "==")
    return secret.encode()


def signature(key: bytes, event_id: str, stamp: str, body: bytes) -> str:
    signed = f"{event_id}.{stamp}.".encode() + body
    return "v1," + base64.b64encode(hmac.new(key, signed, hashlib.sha256).digest()).decode()


class WebhookConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    url: str = Field(description="Where each batch is posted.")
    secret_env: str | None = Field(
        default=None,
        description="Environment variable with the signing secret, ideally whsec_ and base64.",
        json_schema_extra=SECRET,
    )
    headers: dict[str, str] = Field(
        default_factory=dict, description="Extra headers sent with each event."
    )
    exclude: list[str] = Field(
        default_factory=lambda: ["author"], description="Record fields left out of the payload."
    )


def _result(delivery: EventDelivery, sent: int) -> SinkResult:
    if delivery.error:
        return SinkResult(errors=[delivery.error], deliveries=[delivery])
    return SinkResult(sent=sent, deliveries=[delivery])


def _retry_after(response: httpx.Response) -> float | None:
    value = response.headers.get("retry-after", "")
    return float(value) if value.isdigit() and int(value) <= MAX_RETRY_AFTER else None


class WebhookSink:
    name: ClassVar[str] = "webhook"

    def __init__(self, config: WebhookConfig, ctx: Context) -> None:
        ctx.egress.check(config.url)
        self.config = config
        self.ctx = ctx
        self.key = signing_key(env(config.secret_env)) if config.secret_env else None
        self.source = "obsei"

    def bind(self, pipeline: str, key: str) -> None:
        self.source = f"obsei/{pipeline}/{key}"

    def emit(self, event_type: str, data: JsonValue) -> EventDelivery:
        event_id = f"evt_{uuid.uuid4().hex}"
        event = {
            "specversion": "1.0",
            "id": event_id,
            "type": event_type,
            "source": self.source,
            "time": datetime.now(UTC).isoformat(),
            "datacontenttype": "application/json",
            "data": data,
        }
        body = json.dumps(event, ensure_ascii=False, separators=(",", ":")).encode()
        headers = {"Content-Type": "application/json", **self.config.headers}
        status: int | None = None
        error: str | None = None
        wait = BACKOFF_SECONDS
        for attempt in range(1, ATTEMPTS + 1):
            if attempt > 1:
                time.sleep(wait)
                wait *= 2
            stamp = str(int(time.time()))
            headers |= {"webhook-id": event_id, "webhook-timestamp": stamp}
            if self.key:
                headers["webhook-signature"] = signature(self.key, event_id, stamp, body)
            try:
                response = self.ctx.http.post(
                    self.config.url, content=body, headers=headers, extensions=EGRESS
                )
            except httpx.TransportError as exc:
                status, error = None, f"webhook unreachable: {exc}"
                continue
            status = response.status_code
            error = f"webhook returned {status}" if response.is_error else None
            if status != TOO_MANY_REQUESTS and status < SERVER_ERROR:
                break
            wait = _retry_after(response) or wait
        return EventDelivery(
            event_id=event_id,
            event_type=event_type,
            host=httpx.URL(self.config.url).host,
            attempts=attempt,
            status=status,
            error=error,
        )

    def send(self, batch: Sequence[Record]) -> SinkResult:
        exclude = set(self.config.exclude)
        records: list[JsonValue] = [r.model_dump(mode="json", exclude=exclude) for r in batch]
        return _result(self.emit(RECORDS_ROUTED, {"records": records}), len(batch))

    def alert(self, alert: Alert) -> SinkResult:
        return _result(self.emit(ALERT_EVENTS[alert.kind], alert.model_dump(mode="json")), 1)
