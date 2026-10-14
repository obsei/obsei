import base64
import hashlib
import hmac
import json
import time
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

import duckdb
import httpx
import pytest

from obsei import Author, Enrichment, Record, SourceRef
from obsei.core.context import Context
from obsei.core.protocols import Sink
from obsei.core.registry import Registry
from obsei.llm import EgressError, EgressPolicy
from obsei.sinks import register, webhook
from obsei.sinks._common import SinkConfigError
from obsei.sinks.notify import NotifyConfig, NotifySink
from obsei.sinks.slack import render
from obsei.sources.webhook import WebhookSource, WebhookSourceConfig

Handler = Callable[[httpx.Request], httpx.Response]
HYBRID = EgressPolicy(mode="hybrid")


def record(native_id: str, text: str, intent: str = "bug", rating: float = 1) -> Record:
    return Record(
        source=SourceRef(type="appstore", native_id=native_id, url="https://example.com/r"),
        text=text,
        created_at=datetime(2026, 9, 1, tzinfo=UTC),
        rating=rating,
        author=Author(pseudonym="psn_" + "0" * 32),
        enrichments={"classify": Enrichment(value={"intent": intent, "sentiment": "negative"})},
    )


def build(
    name: str,
    config: dict[str, object],
    handler: Handler,
    policy: EgressPolicy = HYBRID,
    *,
    follow_redirects: bool = False,
) -> Sink:
    registry = Registry()
    register(registry)
    http = httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=follow_redirects)
    context = Context(http=http, egress=policy)
    return registry.sink(name).create(json.loads(json.dumps(config)), context)


@pytest.fixture
def sleeps(monkeypatch: pytest.MonkeyPatch) -> list[float]:
    waits: list[float] = []
    monkeypatch.setattr(time, "sleep", waits.append)
    return waits


def test_webhook_sends_signed_events_without_authors(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HOOK_SECRET", "topsecret")
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(204)

    sink = build(
        "webhook", {"url": "http://hooks.internal/obsei", "secret_env": "HOOK_SECRET"}, handler
    )
    result = sink.send([record("1", "Crash")])
    assert result.sent == 1
    request = captured[0]
    event = json.loads(request.content)
    assert event["specversion"] == "1.0"
    assert (event["type"], event["source"]) == ("obsei.records.routed", "obsei")
    assert request.headers["webhook-id"] == event["id"] == result.deliveries[0].event_id
    signed = f"{event['id']}.{request.headers['webhook-timestamp']}.".encode() + request.content
    digest = hmac.new(b"topsecret", signed, hashlib.sha256).digest()
    assert request.headers["webhook-signature"] == f"v1,{base64.b64encode(digest).decode()}"
    intake = WebhookSource(WebhookSourceConfig(secret_env="HOOK_SECRET"), Context())
    intake.verify(request.content, dict(request.headers))
    assert "author" not in event["data"]["records"][0]


def test_webhook_signature_matches_standard_webhooks() -> None:
    key = webhook.signing_key("whsec_MfKQ9r8GKYqrTwjUPD8ILPZIo2LaLaSw")
    body = b'{"test": 2432232314}'
    given = webhook.signature(key, "msg_p5jXN8AQM9LWM0D4loKWxJek", "1614265330", body)
    assert given == "v1,g0hM9SsE+OTPJTGt/tmIKtSyZlE3uFJELVlNIOLJ1OE="


def test_webhook_retries_with_the_same_event_id(sleeps: list[float]) -> None:
    replies = [
        httpx.Response(503),
        httpx.Response(429, headers={"Retry-After": "7"}),
        httpx.Response(200),
    ]
    ids: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        ids.append(json.loads(request.content)["id"])
        return replies.pop(0)

    result = build("webhook", {"url": "http://hooks.internal/x"}, handler).send([record("1", "a")])
    assert result.sent == 1
    assert len(ids) == 3
    assert len(set(ids)) == 1
    assert sleeps == [1.0, 7.0]
    delivery = result.deliveries[0]
    assert (delivery.attempts, delivery.status, delivery.error) == (3, 200, None)


def test_webhook_reports_errors(sleeps: list[float]) -> None:
    sink = build("webhook", {"url": "http://hooks.internal/x"}, lambda _: httpx.Response(503))
    result = sink.send([record("1", "a")])
    assert result.errors == ["webhook returned 503"]
    assert (result.deliveries[0].attempts, sleeps) == (3, [1.0, 2.0])
    refused = build("webhook", {"url": "http://hooks.internal/x"}, lambda _: httpx.Response(400))
    assert refused.send([record("1", "a")]).deliveries[0].attempts == 1

    def down(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    unreachable = build("webhook", {"url": "http://hooks.internal/x"}, down)
    delivery = unreachable.send([record("1", "a")]).deliveries[0]
    assert (delivery.status, delivery.error) == (None, "webhook unreachable: connection refused")


def test_outbound_sinks_respect_egress_policy() -> None:
    with pytest.raises(EgressError):
        build(
            "webhook",
            {"url": "https://hooks.example.com/x"},
            lambda _: httpx.Response(200),
            EgressPolicy(),
        )


def test_slack_filters_and_caps(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SLACK_WEBHOOK_URL", "https://hooks.slack.com/services/T/B/X")
    posts: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        posts.append(json.loads(request.content)["text"])
        return httpx.Response(200)

    sink = build("slack", {"when": {"classify.intent": ["bug"]}, "max_messages": 1}, handler)
    batch = [record("1", "<script> crash"), record("2", "love it", "praise"), record("3", "freeze")]
    result = sink.send(batch)
    assert result.sent == 1
    assert result.skipped == 2
    assert "&lt;script&gt;" in posts[0]
    assert "1 more" in posts[1]
    assert "`bug`" in render(batch[0])


def test_github_issue_sink_is_idempotent(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GITHUB_TOKEN", "t")
    created: list[dict[str, object]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/search/issues":
            exists = "rec_" in request.url.params["q"] and bool(created)
            return httpx.Response(200, json={"total_count": int(exists)})
        created.append(json.loads(request.content))
        return httpx.Response(201, json={})

    sink = build("github_issues", {"repo": "acme/app"}, handler)
    first = sink.send(
        [record("1", "App crashes on login\nsteps..."), record("2", "nice", "praise")]
    )
    assert (first.sent, first.skipped) == (1, 1)
    assert created[0]["title"] == "[bug] App crashes on login"
    assert "obsei:rec_" in str(created[0]["body"])
    again = sink.send([record("1", "App crashes on login\nsteps...")])
    assert (again.sent, again.skipped) == (0, 1)


def test_parquet_overwrites_retried_batch(tmp_path: Path) -> None:
    sink = build("parquet", {"directory": str(tmp_path)}, lambda _: httpx.Response(500))
    batch = [record("1", "Lento"), record("2", "遅い")]
    sink.send(batch)
    sink.send(batch)
    files = list(tmp_path.glob("*.parquet"))
    assert len(files) == 1
    rows = duckdb.read_parquet(str(files[0])).select("text, author_pseudonym").fetchall()
    assert sorted(rows) == [("Lento", None), ("遅い", None)]


def test_egress_applies_to_every_redirect_hop(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HOOK_SECRET", "topsecret")
    hosts: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        hosts.append(request.url.host)
        if request.url.host == "hooks.internal":
            return httpx.Response(307, headers={"Location": "https://collector.example.com/x"})
        return httpx.Response(204)

    sink = build(
        "webhook",
        {"url": "http://hooks.internal/obsei", "secret_env": "HOOK_SECRET"},
        handler,
        EgressPolicy(),
        follow_redirects=True,
    )
    with pytest.raises(EgressError, match=r"collector\.example\.com"):
        sink.send([record("1", "Crash")])
    assert hosts == ["hooks.internal"]


def test_cross_origin_redirects_drop_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HOOK_SECRET", "topsecret")
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        if request.url.host == "hooks.internal":
            return httpx.Response(307, headers={"Location": "http://other.internal/x"})
        return httpx.Response(204)

    sink = build(
        "webhook",
        {
            "url": "http://hooks.internal/obsei",
            "secret_env": "HOOK_SECRET",
            "headers": {"X-Api-Key": "k", "Authorization": "Bearer k"},
        },
        handler,
        follow_redirects=True,
    )
    assert sink.send([record("1", "Crash")]).sent == 1
    first, hop = seen
    assert first.headers["X-Api-Key"] == "k"
    assert "webhook-signature" in first.headers
    assert hop.url.host == "other.internal"
    assert hop.content == first.content
    for name in ("X-Api-Key", "Authorization", "webhook-signature"):
        assert name not in hop.headers


def notify_sink(config: dict[str, object], policy: EgressPolicy = HYBRID) -> NotifySink:
    return NotifySink(NotifyConfig.model_validate(config), Context(egress=policy))


def test_notify_targets_must_pass_egress(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APPRISE_URLS", "tgram://123456:ABCdef/987654")
    with pytest.raises(EgressError, match=r"api\.telegram\.org"):
        notify_sink({}, EgressPolicy())
    notify_sink({}, EgressPolicy(mode="private", allowed_hosts=frozenset({"api.telegram.org"})))
    monkeypatch.setenv("APPRISE_URLS", "mailtos://u:p@example.com?smtp=smtp.example.com")
    with pytest.raises(EgressError, match=r"smtp\.example\.com"):
        notify_sink({}, EgressPolicy())
    monkeypatch.setenv("APPRISE_URLS", "ntfy://alerts")
    with pytest.raises(EgressError, match="hybrid"):
        notify_sink({}, EgressPolicy(mode="private"))
    notify_sink({})
    monkeypatch.setenv("APPRISE_URLS", "nonsense://x")
    with pytest.raises(SinkConfigError, match="invalid Apprise URL"):
        notify_sink({})


def test_notify_sends_one_summary_per_batch(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TEAM_ALERTS", "json://alerts.internal/obsei")
    sink = notify_sink(
        {"urls_env": "TEAM_ALERTS", "when": {"classify.intent": ["bug"]}, "max_items": 1}
    )
    sent: list[dict[str, str]] = []

    def notify(**message: str) -> bool:
        sent.append(message)
        return True

    monkeypatch.setattr(sink.targets[0], "notify", notify)
    batch = [record("1", "Crash on login"), record("2", "love it", "praise"), record("3", "Freeze")]
    result = sink.send(batch)
    assert (result.sent, result.skipped) == (2, 1)
    assert sent[0]["title"] == "obsei: 2 matching feedback item(s)"
    assert sent[0]["body"] == "- [bug] Crash on login\n  https://example.com/r\n…and 1 more."
    assert sink.send([record("2", "love it", "praise")]).skipped == 1
    assert len(sent) == 1
    monkeypatch.setattr(sink.targets[0], "notify", lambda **_: False)
    assert sink.send(batch).errors == ["notify failed for JSON"]
