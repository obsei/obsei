"""Slack slash command (``/obsei <question>``) answered by ``obsei ask`` in the background."""

from __future__ import annotations

import hashlib
import hmac
import os
import time
from urllib.parse import parse_qs

SIGNING_SECRET_ENV = "SLACK_SIGNING_SECRET"  # noqa: S105
MAX_SKEW_SECONDS = 300


class SlackSignatureError(PermissionError):
    pass


def signing_secret() -> bytes | None:
    value = os.environ.get(SIGNING_SECRET_ENV)
    return value.encode() if value else None


def verify(
    secret: bytes, body: bytes, timestamp: str, signature: str, now: float | None = None
) -> None:
    try:
        sent = int(timestamp)
    except ValueError:
        raise SlackSignatureError("bad timestamp") from None
    if abs((now or time.time()) - sent) > MAX_SKEW_SECONDS:
        raise SlackSignatureError("stale request")
    base = b"v0:" + timestamp.encode() + b":" + body
    expected = "v0=" + hmac.new(secret, base, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, signature):
        raise SlackSignatureError("invalid signature")


def command(body: bytes) -> tuple[str, str]:
    """(question, response_url) from a slash-command form body."""
    form = parse_qs(body.decode())
    question = (form.get("text") or [""])[0].strip()
    response_url = (form.get("response_url") or [""])[0]
    return question, response_url


def is_slack_url(url: str) -> bool:
    return url.startswith("https://hooks.slack.com/")
