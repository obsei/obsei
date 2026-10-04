import hashlib
import hmac
import json
import sys
import time
import types
from collections.abc import Iterator
from pathlib import Path
from urllib.parse import urlencode

import httpx
import pytest
from starlette.testclient import TestClient
from typer.testing import CliRunner

from obsei import studio
from obsei.cli import app as cli
from obsei.config import ObseiConfig
from obsei.core.context import Context, LlmEndpoint
from obsei.demo import ISSUES, demo_records, label_demo_themes
from obsei.llm import EgressPolicy
from obsei.llm.embed import LOCAL_MODEL, HashingEmbedder
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


def test_demo_labels_are_curated_and_sources_survive_k(store: Store) -> None:
    label_demo_themes(store, k=5)
    snap = studio.snapshot(store, k=5)
    texts = [r.text.casefold() for r in demo_records()]
    curated = {issue.label for issue in ISSUES.values()}
    for theme in snap.themes:
        assert theme.label is not None
        assert theme.label.split(" (")[0] in curated
        assert theme.sources
        assert not any(t in theme.label.casefold() for t in texts)
    assert {n.label for n in snap.graph.nodes if n.kind == "source"} == {
        "appstore",
        "playstore",
        "zendesk",
        "survey",
        "bluesky",
    }
    login = [t for t in snap.themes if t.label and t.label.startswith("Can't log in")]
    assert len(login) == 3
    assert all(t.last_7_days > t.previous_7_days for t in login)
    assert all(t.last_7_days <= t.previous_7_days for t in snap.themes if t not in login)


class _Vector(list[float]):
    def tolist(self) -> list[float]:
        return list(self)


class IssueTextEmbedding:
    """Stands in for the multilingual model: same issue, close vectors, in any language."""

    offline: list[bool] = []  # noqa: RUF012

    def __init__(self, model_name: str, cache_dir: str | None, local_files_only: bool) -> None:
        IssueTextEmbedding.offline.append(local_files_only)
        records = demo_records()
        keys = list(ISSUES)
        self.vectors = {
            r.text: [float(r.source.native_id.startswith(f"{k}-")) for k in keys]
            + [0.6 * (i == j) for j in range(len(records))]
            for i, r in enumerate(records)
        }

    def embed(self, documents: list[str], batch_size: int) -> Iterator[_Vector]:
        return (_Vector(self.vectors[d]) for d in documents)


@pytest.fixture
def fake_multilingual(monkeypatch: pytest.MonkeyPatch) -> None:
    module = types.ModuleType("fastembed")
    module.TextEmbedding = IssueTextEmbedding  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "fastembed", module)
    monkeypatch.delenv("OBSEI_EGRESS_MODE", raising=False)
    IssueTextEmbedding.offline.clear()


@pytest.mark.usefixtures("fake_multilingual")
def test_demo_with_local_embedder_merges_languages(tmp_path: Path) -> None:
    result = CliRunner().invoke(cli, ["demo", "--embedder", "local", "--out", str(tmp_path)])
    assert result.exit_code == 0, result.output
    assert IssueTextEmbedding.offline == [True]
    data = json.loads((tmp_path / "data.json").read_text(encoding="utf-8"))
    assert data["embedder"] == LOCAL_MODEL
    themes = {t["label"]: t for t in data["themes"]}
    assert set(themes) == {issue.label for issue in ISSUES.values()}
    login = themes["Can't log in"]
    assert login["sources"] == {"appstore": 11, "playstore": 5}
    assert set(login["languages"]) == {"en", "es", "ja"}
    assert login["last_7_days"] > login["previous_7_days"]


def test_demo_rejects_unknown_embedder(tmp_path: Path) -> None:
    result = CliRunner().invoke(cli, ["demo", "--embedder", "nope", "--out", str(tmp_path)])
    assert result.exit_code == 2
    assert "nope" in result.output
    assert not (tmp_path / "data.json").exists()


def test_demo_records_hashing_embedder(tmp_path: Path) -> None:
    result = CliRunner().invoke(cli, ["demo", "--out", str(tmp_path)])
    assert result.exit_code == 0, result.output
    assert json.loads((tmp_path / "data.json").read_text(encoding="utf-8"))["embedder"] == (
        HashingEmbedder().model
    )


def test_k_anonymity_hides_small_groups(store: Store) -> None:
    snap = studio.snapshot(store, k=7)
    assert snap.themes == []
    assert all(b.count >= 7 for b in snap.overview.by_lang)
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
    assert data["demo"] is False
    assert '<meta name="obsei-data" content="data.json" />' in (tmp_path / "index.html").read_text(
        encoding="utf-8"
    )
    studio.export(store, tmp_path, k=5, demo=True)
    assert json.loads((tmp_path / "data.json").read_text(encoding="utf-8"))["demo"] is True
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
    page = client.get("/studio/")
    assert page.status_code == 200
    assert '<meta name="obsei-data" content="api" />' in page.text
    assert "frame-ancestors 'none'" in page.headers["content-security-policy"]
    assert page.headers["x-content-type-options"] == "nosniff"
    assert page.headers["x-frame-options"] == "DENY"
    assert page.headers["referrer-policy"] == "no-referrer"
    denied = client.get("/api/snapshot")
    assert denied.status_code == 401
    assert denied.headers["x-content-type-options"] == "nosniff"
    # HostGuard sits inside SecurityHeaders, so its 421s are hardened too.
    misdirected = client.get("/studio/", headers={"Host": "evil.example"})
    assert misdirected.status_code == 421
    assert misdirected.headers["x-frame-options"] == "DENY"
    assert "frame-ancestors 'none'" in misdirected.headers["content-security-policy"]
    cross = client.get("/studio/", headers={"Origin": "http://evil.example"})
    assert cross.status_code == 421
    assert cross.headers["x-content-type-options"] == "nosniff"
    auth = {"Authorization": f"Bearer {TOKEN}"}
    snap = client.get("/api/snapshot", headers=auth).json()
    assert snap["role"] == "admin"
    assert snap["demo"] is False
    theme = snap["themes"][0]["id"]
    assert snap["evidence"] == {theme_id: [] for theme_id in snap["evidence"]}
    items = client.get(f"/api/themes/{theme}", headers=auth).json()
    assert len(items) == snap["themes"][0]["size"]


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
