"""Post matching feedback to a Slack channel through an incoming webhook."""

from __future__ import annotations

from collections.abc import Sequence
from typing import ClassVar

from pydantic import BaseModel, ConfigDict, Field

from obsei.core.context import EGRESS, Context
from obsei.core.plugin import SECRET
from obsei.core.protocols import Alert, SinkResult
from obsei.core.record import Record
from obsei.routing import Conditions, When
from obsei.sinks._common import SinkConfigError, env, label

MAX_TEXT = 2800
VALID_WEBHOOK = frozenset({"no_text", "invalid_payload"})


class SlackConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    webhook_url_env: str = Field(
        default="SLACK_WEBHOOK_URL",
        description="Environment variable with the Slack incoming webhook URL.",
        json_schema_extra=SECRET,
    )
    when: Conditions = Field(
        default_factory=dict, description='e.g. {"classify.intent": ["bug", "churn_risk"]}'
    )
    max_rating: float | None = Field(default=None, description="Only records rated at most this.")
    max_messages: int = Field(default=20, ge=1, description="Most messages posted per run.")


def _escape(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def render(record: Record) -> str:
    head = [f"*{record.source.type}*"]
    if record.rating is not None:
        head.append("★" * round(record.rating))
    head.extend(
        f"`{tag}`"
        for tag in (label(record, "classify.intent"), label(record, "classify.sentiment"))
        if tag
    )
    text = _escape(record.text)
    if len(text) > MAX_TEXT:
        text = text[:MAX_TEXT] + "…"
    quoted = "\n".join(f"> {line}" for line in text.splitlines())
    link = f"\n<{record.source.url}|open>" if record.source.url else ""
    return f"{' '.join(head)}\n{quoted}{link}"


def render_alert(alert: Alert) -> str:
    return "\n".join(
        [
            f"*{_escape(alert.title)}*",
            *map(_escape, alert.lines),
            *(f"> {_escape(quote)}" for quote in alert.quotes),
        ]
    )


class SlackSink:
    name: ClassVar[str] = "slack"

    def __init__(self, config: SlackConfig, ctx: Context) -> None:
        self.url = env(config.webhook_url_env)
        ctx.egress.check(self.url)
        self.config = config
        self.when = When.parse(config.when, max_rating=config.max_rating)
        self.ctx = ctx

    def send(self, batch: Sequence[Record]) -> SinkResult:
        selected = [r for r in batch if self.when.matches(r)]
        posted = selected[: self.config.max_messages]
        for record in posted:
            response = self.ctx.http.post(
                self.url, json={"text": render(record)}, extensions=EGRESS
            )
            if response.is_error:
                return SinkResult(errors=[f"slack returned {response.status_code}"])
        if len(selected) > len(posted):
            summary = f"…and {len(selected) - len(posted)} more matching feedback item(s)."
            self.ctx.http.post(self.url, json={"text": summary}, extensions=EGRESS)
        return SinkResult(sent=len(posted), skipped=len(batch) - len(posted))

    def verify(self) -> None:
        """A live webhook refuses an empty message with no_text, so nothing is posted."""
        response = self.ctx.http.post(self.url, json={}, extensions=EGRESS)
        if response.text.strip() not in VALID_WEBHOOK:
            raise SinkConfigError(f"slack returned {response.status_code}: {response.text[:80]}")

    def alert(self, alert: Alert) -> SinkResult:
        response = self.ctx.http.post(
            self.url, json={"text": render_alert(alert)}, extensions=EGRESS
        )
        if response.is_error:
            return SinkResult(errors=[f"slack returned {response.status_code}"])
        return SinkResult(sent=1)
