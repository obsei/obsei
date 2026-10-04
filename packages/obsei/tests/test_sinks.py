import hashlib
import hmac
import json
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
from obsei.sinks import register
from obsei.sinks.slack import render

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


def test_webhook_signs_and_omits_authors(monkeypatch: pytest.MonkeyPatch) -> None:
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
    stamp = request.headers["X-Obsei-Timestamp"]
    expected = hmac.new(
        b"topsecret", stamp.encode() + b"." + request.content, hashlib.sha256
    ).hexdigest()
    assert request.headers["X-Obsei-Signature-256"] == f"sha256={expected}"
    payload = json.loads(request.content)
    assert "author" not in payload["records"][0]


def test_webhook_reports_errors() -> None:
    sink = build("webhook", {"url": "http://hooks.internal/x"}, lambda _: httpx.Response(503))
    assert sink.send([record("1", "a")]).errors == ["webhook returned 503"]


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
    assert "X-Obsei-Signature-256" in first.headers
    assert hop.url.host == "other.internal"
    assert hop.content == first.content
    for name in ("X-Api-Key", "Authorization", "X-Obsei-Signature-256"):
        assert name not in hop.headers
