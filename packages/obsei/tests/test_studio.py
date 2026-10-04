import hashlib
import hmac
import json
import threading
import time
from pathlib import Path
from urllib.parse import urlencode

import httpx
import pytest
from starlette.testclient import TestClient

from obsei import studio
from obsei.config import ObseiConfig
from obsei.core.context import Context, LlmEndpoint
from obsei.demo import demo_records
from obsei.llm import EgressPolicy
from obsei.llm.embed import HashingEmbedder
from obsei.serve import create_app
from obsei.slackbot import SlackSignatureError, verify
from obsei.store import Store
from obsei.themes import ThemesConfig, update_themes

TOKEN = "api-token-0123456789"
LOCAL = "http://127.0.0.1:8765"


@pytest.fixture(scope="module")
def store() -> Store:
    s = Store(allow_unencrypted=True)
    s.upsert(demo_records())
    update_themes(s, HashingEmbedder(), ThemesConfig(k_anonymity=5))
    return s


def test_demo_is_redacted_and_multilingual(store: Store) -> None:
    snap = studio.snapshot(store, k=5)
    assert len({b.key for b in snap.overview.by_lang}) >= 8
    assert all(t.size >= 5 for t in snap.themes)
    texts = [e.text for items in snap.evidence.values() for e in items]
    assert any("<PHONE>" in t for t in texts)
    assert not any("sam@example.com" in t or "090-1234" in t for t in texts)
    kept = {n.id for n in snap.graph.nodes}
    assert all(e.source in kept and e.target in kept for e in snap.graph.edges)


def test_k_anonymity_hides_small_groups(store: Store) -> None:
    snap = studio.snapshot(store, k=6)
    assert snap.themes == []
    assert all(b.count >= 6 for b in snap.overview.by_lang)
    assert studio.theme_evidence(store, "thm_unknown", k=1) == []


def test_static_export(store: Store, tmp_path: Path) -> None:
    studio.export(store, tmp_path, k=5)
    assert {p.name for p in tmp_path.iterdir()} == {
        "index.html",
        "app.js",
        "styles.css",
        "logo.png",
        "data.json",
    }
    data = json.loads((tmp_path / "data.json").read_text(encoding="utf-8"))
    assert data["themes"]
    assert "author" not in (tmp_path / "data.json").read_text(encoding="utf-8")


def test_serve_studio_api(store: Store) -> None:
    cfg = ObseiConfig.model_validate(
        {
            "pipelines": [
                {"name": "p", "sources": [{"key": "s", "type": "csv", "config": {"path": "x.csv"}}]}
            ]
        }
    )
    client = TestClient(create_app(cfg, Context(), store, token=TOKEN), base_url=LOCAL)
    assert client.get("/studio/").status_code == 200
    assert client.get("/api/snapshot").status_code == 401
    auth = {"Authorization": f"Bearer {TOKEN}"}
    snap = client.get("/api/snapshot", headers=auth).json()
    theme = snap["themes"][0]["id"]
    assert snap["evidence"] == {theme_id: [] for theme_id in snap["evidence"]}
    items = client.get(f"/api/themes/{theme}", headers=auth).json()
    assert len(items) == 5


def test_slack_signature() -> None:
    secret, body, now = b"s3cret", b"text=hi", 1_800_000_000.0
    sig = "v0=" + hmac.new(secret, b"v0:1800000000:" + body, hashlib.sha256).hexdigest()
    verify(secret, body, "1800000000", sig, now=now)
    with pytest.raises(SlackSignatureError, match="stale"):
        verify(secret, body, "1800000000", sig, now=now + 600)
    with pytest.raises(SlackSignatureError, match="invalid"):
        verify(secret, body + b"x", "1800000000", sig, now=now)
    with pytest.raises(SlackSignatureError, match="invalid"):
        verify(secret, body, "1800000000", "v0=ü", now=now)


def test_slack_command_answers_in_background(store: Store, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SLACK_SIGNING_SECRET", "s3cret")
    posted: list[dict[str, object]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/chat/completions"):
            reply = {"answer": "Login issues lead.", "citations": []}
            return httpx.Response(
                200, json={"choices": [{"message": {"content": json.dumps(reply)}}]}
            )
        posted.append(json.loads(request.content))
        return httpx.Response(200)

    transport = httpx.MockTransport(handler)
    ctx = Context(
        http=httpx.Client(transport=transport),
        egress=EgressPolicy(mode="private", allowed_hosts=frozenset({"hooks.slack.com"})),
        llms={"default": LlmEndpoint(base_url="http://llm.internal/v1", model="m")},
        llm_transport=transport,
    )
    cfg = ObseiConfig.model_validate(
        {
            "pipelines": [
                {"name": "p", "sources": [{"key": "s", "type": "csv", "config": {"path": "x.csv"}}]}
            ]
        }
    )
    client = TestClient(create_app(cfg, ctx, store, token=TOKEN), base_url=LOCAL)
    body = urlencode(
        {"text": "top issues?", "response_url": "https://hooks.slack.com/commands/1"}
    ).encode()
    stamp = str(int(time.time()))
    sig = "v0=" + hmac.new(b"s3cret", f"v0:{stamp}:".encode() + body, hashlib.sha256).hexdigest()
    headers = {"X-Slack-Request-Timestamp": stamp, "X-Slack-Signature": sig}
    response = client.post("/slack/commands", content=body, headers=headers)
    assert response.json()["response_type"] == "ephemeral"
    assert posted == [{"response_type": "in_channel", "text": "Login issues lead."}]


def slack_request(text: str) -> tuple[bytes, dict[str, str]]:
    body = urlencode({"text": text, "response_url": "https://hooks.slack.com/commands/1"}).encode()
    stamp = str(int(time.time()))
    sig = "v0=" + hmac.new(b"s3cret", f"v0:{stamp}:".encode() + body, hashlib.sha256).hexdigest()
    return body, {"X-Slack-Request-Timestamp": stamp, "X-Slack-Signature": sig}


def test_slack_command_explains_blocked_egress(
    store: Store, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SLACK_SIGNING_SECRET", "s3cret")
    cfg = ObseiConfig.model_validate(
        {
            "pipelines": [
                {"name": "p", "sources": [{"key": "s", "type": "csv", "config": {"path": "x.csv"}}]}
            ]
        }
    )
    client = TestClient(create_app(cfg, Context(), store, token=TOKEN), base_url=LOCAL)
    body, headers = slack_request("top issues?")
    response = client.post("/slack/commands", content=body, headers=headers)
    assert response.status_code == 200
    reply = response.json()
    assert reply["response_type"] == "ephemeral"
    assert "air_gapped egress policy blocks hooks.slack.com" in reply["text"]


def test_slow_model_does_not_block_other_requests(store: Store) -> None:
    entered, release = threading.Event(), threading.Event()

    def handler(request: httpx.Request) -> httpx.Response:
        entered.set()
        release.wait(10)
        reply = {"answer": "Login issues lead.", "citations": []}
        return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps(reply)}}]})

    ctx = Context(
        llms={"default": LlmEndpoint(base_url="http://llm.internal/v1", model="m")},
        llm_transport=httpx.MockTransport(handler),
    )
    cfg = ObseiConfig.model_validate(
        {
            "pipelines": [
                {"name": "p", "sources": [{"key": "s", "type": "csv", "config": {"path": "x.csv"}}]}
            ],
        }
    )
    auth = {"Authorization": f"Bearer {TOKEN}"}
    answers: list[int] = []
    with TestClient(create_app(cfg, ctx, store, token=TOKEN), base_url=LOCAL) as client:
        asking = threading.Thread(
            target=lambda: answers.append(
                client.post("/api/ask", json={"question": "top?"}, headers=auth).status_code
            )
        )
        asking.start()
        try:
            assert entered.wait(10)
            started = time.monotonic()
            assert client.get("/api/snapshot", headers=auth).status_code == 200
            assert client.get(f"/api/themes/{_any_theme(store)}", headers=auth).status_code == 200
            assert time.monotonic() - started < 5
            assert not release.is_set()
        finally:
            release.set()
            asking.join(10)
    assert answers == [200]


def _any_theme(store: Store) -> str:
    return studio.snapshot(store, k=5).themes[0].id
