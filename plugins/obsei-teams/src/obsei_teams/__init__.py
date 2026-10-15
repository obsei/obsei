"""Post matching feedback to a Microsoft Teams channel as an Adaptive Card through a
Power Automate Workflows webhook."""

from __future__ import annotations

from collections.abc import Sequence
from typing import ClassVar
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, JsonValue

from obsei.core.context import EGRESS, Context
from obsei.core.plugin import factory
from obsei.core.protocols import Alert, SinkResult
from obsei.core.record import Record
from obsei.core.registry import Registry
from obsei.routing import Conditions, When
from obsei.sinks._common import env, label

CARD_TYPE = "application/vnd.microsoft.card.adaptive"
CARD_VERSION = "1.4"
MAX_STARS = 5


class TeamsConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    webhook_url_env: str = "TEAMS_WEBHOOK_URL"
    title: str = "New customer feedback"
    when: Conditions = Field(
        default_factory=dict, description='e.g. {"classify.sentiment": ["negative"]}'
    )
    max_rating: float | None = None
    max_records: int = Field(default=10, ge=1, le=25, description="Records per card.")
    max_text: int = Field(default=600, ge=50, le=4000)


def _text(value: str, *, weight: str | None = None, subtle: bool = False) -> dict[str, JsonValue]:
    block: dict[str, JsonValue] = {"type": "TextBlock", "text": value, "wrap": True}
    if weight:
        block["weight"] = weight
    if subtle:
        block["isSubtle"] = True
    return block


def _plain(value: str, *, weight: str | None = None) -> dict[str, JsonValue]:
    """Feedback goes in a TextRun, which Teams never renders as markdown, so customer text
    cannot add links or formatting."""
    run: dict[str, JsonValue] = {"type": "TextRun", "text": value}
    if weight:
        run["weight"] = weight
    return {"type": "RichTextBlock", "inlines": [run]}


def element(record: Record, max_text: int) -> dict[str, JsonValue]:
    head = [f"{record.source.type}/{record.source.instance}"]
    if record.rating is not None:
        stars = round(record.rating)
        head.append("★" * stars if 1 <= stars <= MAX_STARS else f"rating {record.rating:g}")
    head.extend(
        tag
        for tag in (label(record, "classify.sentiment"), label(record, "classify.intent"))
        if tag
    )
    text = record.text if len(record.text) <= max_text else record.text[:max_text] + "…"
    items: list[JsonValue] = [_text(" · ".join(head), weight="Bolder", subtle=True), _plain(text)]
    url = record.source.url
    if url and urlsplit(url).scheme in {"http", "https"}:
        items.append(
            {
                "type": "ActionSet",
                "actions": [{"type": "Action.OpenUrl", "title": "Open", "url": url}],
            }
        )
    return {"type": "Container", "separator": True, "spacing": "Medium", "items": items}


def card(title: str, records: Sequence[Record], more: int, max_text: int) -> dict[str, JsonValue]:
    body: list[JsonValue] = [_text(title, weight="Bolder")]
    body.extend(element(r, max_text) for r in records)
    if more:
        body.append(_text(f"…and {more} more matching feedback item(s).", subtle=True))
    return _message(body)


def alert_card(alert: Alert) -> dict[str, JsonValue]:
    """Theme labels and quotes derive from customer text, so they stay plain text too."""
    body: list[JsonValue] = [_plain(alert.title, weight="Bolder")]
    body.extend(_plain(line) for line in alert.lines)
    body.extend(_plain(f"“{quote}”") for quote in alert.quotes)
    return _message(body)


def _message(body: list[JsonValue]) -> dict[str, JsonValue]:
    return {
        "type": "message",
        "attachments": [
            {
                "contentType": CARD_TYPE,
                "contentUrl": None,
                "content": {
                    "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
                    "type": "AdaptiveCard",
                    "version": CARD_VERSION,
                    "msteams": {"width": "Full"},
                    "body": body,
                },
            }
        ],
    }


class TeamsSink:
    name: ClassVar[str] = "teams"

    def __init__(self, config: TeamsConfig, ctx: Context) -> None:
        self.url = env(config.webhook_url_env)
        ctx.egress.check(self.url)
        self.config = config
        self.when = When.parse(config.when, max_rating=config.max_rating)
        self.ctx = ctx

    def send(self, batch: Sequence[Record]) -> SinkResult:
        c = self.config
        selected = [r for r in batch if self.when.matches(r)]
        if not selected:
            return SinkResult(skipped=len(batch))
        posted = selected[: c.max_records]
        message = card(c.title, posted, len(selected) - len(posted), c.max_text)
        result = self._post(message, len(posted))
        return result.model_copy(update={"skipped": len(batch) - len(posted)})

    def alert(self, alert: Alert) -> SinkResult:
        return self._post(alert_card(alert), 1)

    def _post(self, message: dict[str, JsonValue], sent: int) -> SinkResult:
        response = self.ctx.http.post(self.url, json=message, extensions=EGRESS)
        if response.is_error:
            return SinkResult(errors=[f"teams returned {response.status_code}"])
        return SinkResult(sent=sent)


def register(registry: Registry) -> None:
    registry.add_sink("teams", factory(TeamsConfig, TeamsSink))
