import json
from datetime import UTC, datetime
from typing import Any

import httpx
import pytest
from pydantic import JsonValue

from obsei.core.context import Context
from obsei.core.protocols import Alert, Alerts, Sink, Verifies
from obsei.core.record import Enrichment, Record, SourceRef
from obsei.core.registry import Registry
from obsei.llm.egress import EgressError, EgressPolicy
from obsei.sinks._common import SinkConfigError
from obsei_telegram import register

TOKEN = "123456:TEST-token-never-real"
CHAT = -1001234567890
ALLOW = EgressPolicy(mode="private", allowed_hosts=frozenset({"api.telegram.org"}))


def record(
    native_id: str,
    text: str,
    *,
    rating: float | None = None,
    url: str | None = None,
    sentiment: str | None = None,
) -> Record:
    item = Record(
        source=SourceRef(type="appstore", instance="us", native_id=native_id, url=url),
        text=text,
        created_at=datetime(2026, 9, 1, tzinfo=UTC),
        rating=rating,
    )
    if sentiment:
        value = {"sentiment": sentiment, "intent": "bug"}
        item = item.with_enrichment("classify", Enrichment(value=value))
    return item


class Bot:
    """A fake Bot API that records each call and answers with ``status`` and ``body``."""

    def __init__(
        self,
        status: int = 200,
        body: JsonValue = None,
        error: httpx.HTTPError | None = None,
        results: dict[str, JsonValue] | None = None,
    ) -> None:
        self.status = status
        self.body = body if body is not None else {"ok": status < 400, "result": {}}
        self.error = error
        self.results = results or {}
        self.requests: list[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if self.error:
            raise self.error
        method = request.url.path.rsplit("/", 1)[1]
        if method in self.results:
            return httpx.Response(200, json={"ok": True, "result": self.results[method]})
        if isinstance(self.body, str):
            return httpx.Response(self.status, text=self.body)
        return httpx.Response(self.status, json=self.body)

    def method(self, index: int = 0) -> str:
        return self.requests[index].url.path.rsplit("/", 1)[1]

    def payload(self, index: int = 0) -> Any:
        return json.loads(self.requests[index].content)


def sink(bot: Bot, egress: EgressPolicy = ALLOW, **config: JsonValue) -> Sink:
    registry = Registry()
    register(registry)
    ctx = Context(http=httpx.Client(transport=httpx.MockTransport(bot)), egress=egress)
    return registry.sink("telegram").create({"chat_id": CHAT, **config}, ctx)


@pytest.fixture(autouse=True)
def bot_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", TOKEN)


def test_posts_one_html_message_per_record() -> None:
    bot = Bot()
    telegram = sink(bot, when={"classify.sentiment": ["negative"]})
    batch = [
        record(
            "1",
            "Crashes on login",
            rating=1,
            url="https://apps.apple.com/r/1",
            sentiment="negative",
        ),
        record(
            "2",
            '<a href="https://evil.example">win</a> & ' + "x" * 1100,
            sentiment="negative",
            url="javascript:alert(1)",
        ),
        record("3", "Love it", rating=5, sentiment="positive"),
    ]
    result = telegram.send(batch)
    assert (result.sent, result.skipped, result.errors) == (2, 1, [])
    assert [bot.method(i) for i in range(2)] == ["sendMessage"] * 2
    request = bot.requests[0]
    assert request.url.path == f"/bot{TOKEN}/sendMessage"
    assert request.extensions["obsei_egress"] is True
    first = bot.payload(0)
    assert first == {
        "chat_id": CHAT,
        "text": (
            "<b>appstore/us · ★ · negative · bug</b>\n"
            "Crashes on login\n"
            '<a href="https://apps.apple.com/r/1">Open</a>'
        ),
        "parse_mode": "HTML",
        "link_preview_options": {"is_disabled": True},
    }
    second = bot.payload(1)["text"]
    assert "&lt;a href=&quot;https://evil.example&quot;&gt;win&lt;/a&gt; &amp; " in second
    assert "<a " not in second
    assert second.endswith("x…")


def test_caps_messages_and_summarises_the_rest() -> None:
    bot = Bot()
    telegram = sink(bot, max_messages=2, max_rating=2)
    batch = [record(str(i), f"bad {i}", rating=10 if i == 0 else 1) for i in range(5)]
    result = telegram.send(batch)
    assert (result.sent, result.skipped) == (2, 3)
    assert len(bot.requests) == 3
    assert bot.payload(2)["text"] == "…and 2 more matching feedback item(s)."


def test_nothing_selected_posts_nothing() -> None:
    bot = Bot()
    result = sink(bot, max_rating=2).send([record("1", "fine", rating=4)])
    assert (result.sent, result.skipped) == (0, 1)
    assert bot.requests == []


def test_rating_outside_star_range_is_numeric_and_chat_can_be_a_name() -> None:
    bot = Bot()
    sink(bot, chat_id="@mychannel").send([record("1", "meh", rating=7)])
    payload = bot.payload()
    assert payload["chat_id"] == "@mychannel"
    assert payload["text"].startswith("<b>appstore/us · rating 7</b>")


@pytest.mark.parametrize(
    ("bot", "error"),
    [
        (
            Bot(400, {"ok": False, "description": "Bad Request: chat not found"}),
            "telegram returned 400: Bad Request: chat not found",
        ),
        (Bot(502, "Bad gateway"), "telegram returned 502"),
        (Bot(error=httpx.ConnectError("boom")), "telegram request failed: ConnectError"),
    ],
)
def test_errors_never_contain_the_token(bot: Bot, error: str) -> None:
    result = sink(bot).send([record("1", "x"), record("2", "y")])
    assert (result.sent, result.errors) == (0, [error])
    assert len(bot.requests) == 1
    assert TOKEN not in error


def test_egress_and_missing_token(monkeypatch: pytest.MonkeyPatch) -> None:
    with pytest.raises(EgressError, match="blocked") as blocked:
        sink(Bot(), egress=EgressPolicy())
    assert TOKEN not in str(blocked.value)
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN")
    with pytest.raises(SinkConfigError, match="TELEGRAM_BOT_TOKEN"):
        sink(Bot())


def member(status: str, **fields: JsonValue) -> Bot:
    return Bot(results={"getMe": {"id": 42}, "getChatMember": {"status": status, **fields}})


def test_verify_checks_the_bot_can_post_without_posting() -> None:
    bot = member("member")
    telegram = sink(bot)
    assert isinstance(telegram, Verifies)
    telegram.verify()
    assert [bot.method(i) for i in range(2)] == ["getMe", "getChatMember"]
    assert bot.payload(1) == {"chat_id": CHAT, "user_id": 42}


@pytest.mark.parametrize(
    "bot",
    [
        member("creator"),
        member("administrator"),
        member("administrator", can_post_messages=True),
        member("restricted", is_member=True, can_send_messages=True),
    ],
)
def test_verify_accepts_members_who_can_post(bot: Bot) -> None:
    telegram = sink(bot)
    assert isinstance(telegram, Verifies)
    telegram.verify()


@pytest.mark.parametrize(
    ("bot", "status"),
    [
        (member("kicked"), "kicked"),
        (member("left"), "left"),
        (member("administrator", can_post_messages=False), "administrator"),
        (member("restricted", is_member=True, can_send_messages=False), "restricted"),
    ],
)
def test_verify_rejects_a_bot_that_cannot_post(bot: Bot, status: str) -> None:
    telegram = sink(bot)
    assert isinstance(telegram, Verifies)
    with pytest.raises(SinkConfigError, match=f"status: {status}"):
        telegram.verify()


def test_verify_reports_api_errors_without_the_token() -> None:
    failing = sink(Bot(401, {"ok": False, "description": "Unauthorized"}))
    assert isinstance(failing, Verifies)
    with pytest.raises(SinkConfigError, match="telegram returned 401: Unauthorized") as error:
        failing.verify()
    assert TOKEN not in str(error.value)


def test_alert_is_one_escaped_message() -> None:
    bot = Bot()
    telegram = sink(bot)
    assert isinstance(telegram, Alerts)
    alert = Alert(
        alert="queue",
        kind="theme_spike",
        key="thm_1",
        title="Theme spiking: <Login>",
        lines=["15 records", "Owner: @ana"],
        quotes=["I cannot <b>log in</b>"],
    )
    assert telegram.alert(alert).sent == 1
    assert bot.payload()["text"] == (
        "<b>Theme spiking: &lt;Login&gt;</b>\n"
        "15 records\n"
        "Owner: @ana\n"
        "“I cannot &lt;b&gt;log in&lt;/b&gt;”"
    )
    failing = sink(Bot(500))
    assert isinstance(failing, Alerts)
    assert failing.alert(alert).errors == ["telegram returned 500"]
