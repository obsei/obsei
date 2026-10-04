import hashlib
import hmac
import json
import sys
import threading
import time
import types
from collections.abc import Iterator
from importlib import resources
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
from obsei.demo import (
    DECISION_MODEL,
    ISSUES,
    decision_labels,
    demo_records,
    label_demo_themes,
    raw_demo_records,
    redacted_demo_records,
    stored_labels,
)
from obsei.evidence import ThemeInfo
from obsei.llm import EgressPolicy
from obsei.llm.decision import DecisionClient
from obsei.llm.embed import LOCAL_MODEL, HashingEmbedder
from obsei.serve import create_app
from obsei.slackbot import SlackSignatureError, verify
from obsei.store import Store
from obsei.themes import ThemesConfig, update_themes

TOKEN = "api-token-0123456789"
LOCAL = "http://127.0.0.1:8765"
RAW_PII = (
    "sam.rivera@example.com",
    "090-1234-5678",
    "4111 1111 1111 1111",
    "482.915.736-46",
    "DE89 3704",
    "7181 9093 7865",
    "٠٥٠١٢٣٤٥٦٧",
    "+49 151",
)
DEMO_PLACEHOLDERS = {"EMAIL", "PHONE", "CARD", "IBAN", "IN_AADHAAR", "BR_CPF"}


def rising(theme: ThemeInfo) -> bool:
    """Studio's rule (charts.ts isRising)."""
    return theme.last_7_days >= 3 and theme.last_7_days >= 2 * max(1, theme.previous_7_days)


@pytest.fixture(scope="module")
def store() -> Store:
    s = Store(allow_unencrypted=True)
    s.upsert(demo_records())
    update_themes(s, HashingEmbedder(), ThemesConfig(k_anonymity=5))
    return s


def test_demo_is_redacted_and_multilingual(store: Store) -> None:
    snap = studio.snapshot(store, k=5, evidence_per_theme=50)
    assert {b.key for b in snap.overview.by_lang} == {
        "en", "es", "ja", "ko", "ar", "pt", "de", "hi", "it", "fr", "id"
    }  # fmt: skip
    assert all(t.size >= 5 for t in snap.themes)
    texts = [e.text for items in snap.evidence.values() for e in items]
    assert any("<PHONE>" in t for t in texts)
    dumped = snap.model_dump_json()
    assert not any(pii in dumped for pii in RAW_PII)
    assert all(any(pii in r.text for r in raw_demo_records()) for pii in RAW_PII)
    kept = {n.id for n in snap.graph.nodes}
    assert all(e.source in kept and e.target in kept for e in snap.graph.edges)


def test_privacy_panel_aggregates(store: Store) -> None:
    privacy = studio.snapshot(store, k=5).privacy
    assert set(privacy.placeholders) == DEMO_PLACEHOLDERS
    assert privacy.placeholders["PHONE"] == 3
    assert privacy.redacted_records == 8
    records = demo_records()
    assert privacy.pseudonymised_authors == len({r.author.pseudonym for r in records if r.author})
    assert 0 < privacy.pseudonymised_authors < len(records)
    assert privacy.k_anonymity == 5
    assert privacy.egress is None
    strict = studio.snapshot(store, k=30)
    assert strict.privacy.hidden_themes == len(studio.snapshot(store, k=1).themes)
    assert strict.privacy.hidden_groups > 0


def test_demo_labels_come_from_the_decision_model(store: Store) -> None:
    labels = stored_labels()
    assert {r.source.native_id for r in raw_demo_records()} == set(labels)
    assert {e.model for e in labels.values()} == {DECISION_MODEL}
    text = (resources.files("obsei") / "demo_labels.json").read_text(encoding="utf-8")
    assert "http" not in text
    assert not any(pii in text for pii in RAW_PII)
    snap = studio.snapshot(store, k=5, evidence_per_theme=50)
    decisions = snap.overview.decisions
    assert decisions is not None
    assert decisions.model == DECISION_MODEL
    assert decisions.labelled == len(labels)
    assert 0 < decisions.review < decisions.labelled
    assert set(decisions.fields) == {"team", "urgency", "angry"}
    assert all(c.count >= 5 for counts in decisions.fields.values() for c in counts)
    assert all(c.score is not None for c in decisions.fields["urgency"])
    item = next(e for items in snap.evidence.values() for e in items)
    assert set(item.fields) == {"team", "urgency", "angry"}
    assert {"sentiment", "intent", "team", "urgency", "angry"} <= set(item.confidences)
    assert item.review is not None


def test_demo_decision_labels_use_the_decision_api() -> None:
    asked: list[dict[str, object]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        asked.append(body)
        answers: dict[str, object] = {}
        for name, q in body["questions"].items():
            options = list(q.get("criteria") or [])
            if q["type"] == "score":
                answers[name] = {
                    "type": "score",
                    "score": 1.0,
                    "probabilities": {str(i): float(i == 1) for i in range(len(options))},
                    "confidence": 0.9,
                }
            else:
                answers[name] = {
                    "type": "choice",
                    "choice": options[0],
                    "probabilities": {o: float(i == 0) for i, o in enumerate(options)},
                    "confidence": 0.95,
                }
        return httpx.Response(200, json={"model": "/models/local.gguf", "answers": answers})

    client = DecisionClient(
        url="http://127.0.0.1:9/decide",
        policy=EgressPolicy(),
        transport=httpx.MockTransport(handler),
    )
    records = redacted_demo_records()[:3]
    labels = decision_labels(records, client, model=DECISION_MODEL)
    assert len(asked) == 3
    assert all("@example.com" not in str(b["state"]) for b in asked)
    first = labels[records[0].source.native_id]
    assert first.model == DECISION_MODEL
    assert isinstance(first.value, dict)
    assert first.value["fields"] == {"team": "engineering", "urgency": "this week", "angry": True}


def test_demo_save_labels_needs_a_decision_model(tmp_path: Path) -> None:
    result = CliRunner().invoke(
        cli, ["demo", "--out", str(tmp_path), "--save-labels", str(tmp_path / "l.json")]
    )
    assert result.exit_code == 2
    assert not (tmp_path / "l.json").exists()


def test_demo_records_are_routed_by_the_example_routes(store: Store) -> None:
    rules = {r.source.native_id: r.enrichments["route"].value for r in demo_records()}
    assert {v["rule"] for v in rules.values() if isinstance(v, dict)} == {
        "review",
        "urgent-bugs",
        "billing",
        "default",
    }
    routes = {b.key: b.count for b in studio.snapshot(store, k=5).overview.by_route}
    assert set(routes) == {"review", "urgent-bugs", "billing", "default"}
    assert sum(routes.values()) == len(rules)


def test_theme_weekly_counts_match_trends(store: Store) -> None:
    for theme in studio.snapshot(store, k=5).themes:
        assert len(theme.weekly) == 8
        assert theme.weekly[-1] == theme.last_7_days
        assert theme.weekly[-2] == theme.previous_7_days
        assert sum(theme.weekly) <= theme.size


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
        "github",
    }
    login = [t for t in snap.themes if t.label and t.label.startswith("Can't log in")]
    assert login
    assert all(rising(t) for t in login)
    assert not any(rising(t) for t in snap.themes if t not in login)


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
    assert login["sources"] == {"appstore": 12, "playstore": 11, "zendesk": 6}
    assert set(login["languages"]) == {"en", "es", "ja", "ko", "ar"}
    assert rising(ThemeInfo.model_validate(login))
    assert not any(rising(ThemeInfo.model_validate(t)) for t in data["themes"] if t is not login)
    assert data["demo"] is True
    assert set(data["privacy"]["placeholders"]) == DEMO_PLACEHOLDERS
    showcase = data["showcase"]
    for example in showcase["redactions"]:
        assert example["raw"] != example["stored"]
        assert "<" in example["stored"]
        assert not any(pii in example["stored"] for pii in RAW_PII)
    shown = {e["id"] for items in data["evidence"].values() for e in items}
    assert len(showcase["answers"]) == 3
    for answer in showcase["answers"]:
        assert answer["citations"]
        assert set(answer["citations"]) <= shown
    assert f"{login['last_7_days']} reports in the last 7 days" in showcase["answers"][0]["answer"]


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
    snap = studio.snapshot(store, k=30)
    assert snap.themes == []
    assert all(b.count >= 30 for b in snap.overview.by_lang)
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
    assert data["showcase"] is None
    assert data["privacy"]["egress"] is None
    text = (tmp_path / "data.json").read_text(encoding="utf-8")
    assert "psn_" not in text
    assert not any(pii in text for pii in RAW_PII)


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
    assert snap["showcase"] is None
    assert snap["privacy"]["egress"] == "air_gapped"
    assert set(snap["privacy"]["placeholders"]) == DEMO_PLACEHOLDERS
    theme = snap["themes"][0]["id"]
    assert snap["evidence"] == {theme_id: [] for theme_id in snap["evidence"]}
    items = client.get(f"/api/themes/{theme}", headers=auth).json()
    assert len(items) == snap["themes"][0]["size"] - snap["themes"][0]["duplicates"]


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
            theme = _any_theme(store)
            started = time.monotonic()
            assert client.get("/api/snapshot", headers=auth).status_code == 200
            assert client.get(f"/api/themes/{theme}", headers=auth).status_code == 200
            assert time.monotonic() - started < 5
            assert not release.is_set()
        finally:
            release.set()
            asking.join(10)
    assert answers == [200]


def _any_theme(store: Store) -> str:
    return studio.snapshot(store, k=5).themes[0].id
