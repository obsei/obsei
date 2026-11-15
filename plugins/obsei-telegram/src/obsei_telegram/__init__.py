"""Post matching feedback to a Telegram chat through the Bot API's ``sendMessage``."""

from __future__ import annotations

import html
from collections.abc import Sequence
from typing import ClassVar, TypeVar
from urllib.parse import urlsplit

import httpx
from pydantic import BaseModel, ConfigDict, Field, JsonValue, ValidationError

from obsei.core.context import EGRESS, Context
from obsei.core.plugin import SECRET, Catalog, factory
from obsei.core.protocols import Alert, SinkResult
from obsei.core.record import Record
from obsei.core.registry import Registry
from obsei.routing import Conditions, When
from obsei.sinks._common import SinkConfigError, env, label

API = "https://api.telegram.org"
MAX_STARS = 5
MAX_DESCRIPTION = 80


class TelegramConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    bot_token_env: str = Field(
        default="TELEGRAM_BOT_TOKEN",
        description="Environment variable with the bot token from @BotFather.",
        json_schema_extra=SECRET,
    )
    chat_id: int | str = Field(description='Chat to post to, e.g. -1001234567890 or "@mychannel".')
    when: Conditions = Field(
        default_factory=dict, description='e.g. {"classify.sentiment": ["negative"]}'
    )
    max_rating: float | None = Field(default=None, description="Only records rated at most this.")
    max_messages: int = Field(
        default=10,
        ge=1,
        le=20,
        description="Most messages posted per run; groups allow about 20 a minute.",
    )
    max_text: int = Field(
        default=1000,
        ge=50,
        le=2000,
        description="Characters of each record's text shown. Telegram counts its 4096 limit "
        "in UTF-16 units, so an emoji can count twice.",
    )


def render(record: Record, max_text: int) -> str:
    """Customer text is HTML-escaped, so it cannot add formatting or hidden links (Telegram still
    links bare URLs). ``max_text`` keeps each message under Telegram's 4096 limit."""
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
    lines = [f"<b>{html.escape(' · '.join(head))}</b>", html.escape(text)]
    url = record.source.url
    if url and urlsplit(url).scheme in {"http", "https"}:
        lines.append(f'<a href="{html.escape(url)}">Open</a>')
    return "\n".join(lines)


def render_alert(alert: Alert) -> str:
    """Theme labels and quotes derive from customer text, so they are escaped too."""
    return "\n".join(
        [
            f"<b>{html.escape(alert.title)}</b>",
            *map(html.escape, alert.lines),
            *(f"“{html.escape(quote)}”" for quote in alert.quotes),
        ]
    )


class _Reply(BaseModel):
    """A Bot API reply; fields the sink does not use are ignored."""

    ok: bool = False
    result: JsonValue = None
    description: str | None = None


class _User(BaseModel):
    id: int


class _ChatMember(BaseModel):
    status: str
    is_member: bool | None = None
    can_send_messages: bool | None = None
    can_post_messages: bool | None = None

    def can_post(self) -> bool:
        """``can_post_messages`` is only set for channel administrators."""
        if self.status in {"creator", "member"}:
            return True
        if self.status == "administrator":
            return self.can_post_messages is not False
        if self.status == "restricted":
            return bool(self.is_member and self.can_send_messages)
        return False


_Model = TypeVar("_Model", bound=BaseModel)


class TelegramSink:
    name: ClassVar[str] = "telegram"

    def __init__(self, config: TelegramConfig, ctx: Context) -> None:
        self.token = env(config.bot_token_env)
        ctx.egress.check(API)
        self.config = config
        self.when = When.parse(config.when, max_rating=config.max_rating)
        self.ctx = ctx

    def send(self, batch: Sequence[Record]) -> SinkResult:
        c = self.config
        selected = [r for r in batch if self.when.matches(r)]
        posted = selected[: c.max_messages]
        for sent, record in enumerate(posted):
            _, error = self._call("sendMessage", self._message(render(record, c.max_text)))
            if error:
                return SinkResult(sent=sent, skipped=len(batch) - len(posted), errors=[error])
        if len(selected) > len(posted):
            summary = f"…and {len(selected) - len(posted)} more matching feedback item(s)."
            self._call("sendMessage", self._message(html.escape(summary)))
        return SinkResult(sent=len(posted), skipped=len(batch) - len(posted))

    def verify(self) -> None:
        """Checks the token and that the bot can post in the chat, posting nothing."""
        me = self._result("getMe", {}, _User)
        member = self._result(
            "getChatMember", {"chat_id": self.config.chat_id, "user_id": me.id}, _ChatMember
        )
        if not member.can_post():
            raise SinkConfigError(
                f"the bot cannot post in chat {self.config.chat_id} (status: {member.status}); "
                "add it to the chat, or make it an admin that can post in a channel"
            )

    def alert(self, alert: Alert) -> SinkResult:
        _, error = self._call("sendMessage", self._message(render_alert(alert)))
        return SinkResult(errors=[error]) if error else SinkResult(sent=1)

    def _message(self, text: str) -> dict[str, JsonValue]:
        return {
            "chat_id": self.config.chat_id,
            "text": text,
            "parse_mode": "HTML",
            "link_preview_options": {"is_disabled": True},
        }

    def _call(self, method: str, payload: dict[str, JsonValue]) -> tuple[_Reply, str | None]:
        """Calls a Bot API method and returns its reply and an error message, or None on
        success. The token is part of the URL, so errors carry only the status and Telegram's
        description."""
        url = f"{API}/bot{self.token}/{method}"
        try:
            response = self.ctx.http.post(url, json=payload, extensions=EGRESS)
        except httpx.HTTPError as e:
            return _Reply(), f"telegram request failed: {type(e).__name__}"
        try:
            reply = _Reply.model_validate_json(response.content)
        except ValidationError:
            reply = _Reply()
        if response.is_error or not reply.ok:
            description = (reply.description or "")[:MAX_DESCRIPTION]
            return reply, f"telegram returned {response.status_code}" + (
                f": {description}" if description else ""
            )
        return reply, None

    def _result(self, method: str, payload: dict[str, JsonValue], model: type[_Model]) -> _Model:
        """The result of a call that must succeed, for ``verify()``."""
        reply, error = self._call(method, payload)
        if error:
            raise SinkConfigError(error)
        try:
            return model.model_validate(reply.result)
        except ValidationError:
            raise SinkConfigError(f"telegram sent an unexpected {method} reply") from None


def register(registry: Registry) -> None:
    registry.add_sink(
        "telegram",
        factory(
            TelegramConfig,
            TelegramSink,
            Catalog(
                title="Telegram chat",
                category="chat",
                docs_url="https://github.com/obsei/obsei/tree/master/plugins/obsei-telegram",
                help_url="https://core.telegram.org/bots/features#botfather",
            ),
        ),
    )
