import hashlib
import hmac
import json

import pytest
from starlette.testclient import TestClient

from obsei.access import HostAllowlist
from obsei.config import ObseiConfig, build_context
from obsei.serve import create_app
from obsei.store import Store

SECRET = "hook-secret-0123456789"
API_TOKEN = "api-token-0123456789"
LOCAL = "http://127.0.0.1:8765"


def config() -> ObseiConfig:
    return ObseiConfig.model_validate(
        {
            "pipelines": [
                {
                    "name": "support",
                    "sources": [
                        {
                            "key": "tickets",
                            "type": "webhook",
                            "config": {
                                "secret_env": "HOOK_SECRET",
                                "items_path": "tickets",
                                "fields": {
                                    "text": "body",
                                    "id": "id",
                                    "lang": "locale",
                                    "created_at": "at",
                                },
                            },
                        }
                    ],
                }
            ]
        }
    )


@pytest.fixture
def store() -> Store:
    return Store(allow_unencrypted=True)


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch, store: Store) -> TestClient:
    monkeypatch.setenv("HOOK_SECRET", SECRET)
    cfg = config()
    app = create_app(cfg, build_context(cfg), store, token=API_TOKEN)
    return TestClient(app, base_url=LOCAL)


def signed(body: bytes) -> dict[str, str]:
    digest = hmac.new(SECRET.encode(), body, hashlib.sha256).hexdigest()
    return {"X-Obsei-Signature-256": f"sha256={digest}", "Content-Type": "application/json"}


def test_health_is_public(client: TestClient) -> None:
    assert client.get("/healthz").json() == {"status": "ok"}


def test_ingest_verifies_signature_and_redacts(client: TestClient, store: Store) -> None:
    body = json.dumps(
        {
            "tickets": [
                {
                    "id": "t1",
                    "at": "2026-09-01T08:00:00+02:00",
                    "body": "Erreur de paiement, écrivez à paul@example.fr",
                    "locale": "fr",
                }
            ]
        }
    ).encode()
    assert client.post("/ingest/support/tickets", content=body).status_code == 401
    accepted = client.post("/ingest/support/tickets", content=body, headers=signed(body))
    assert accepted.status_code == 202
    assert accepted.json() == {"received": 1, "skipped": 0, "stored": 1}
    again = client.post("/ingest/support/tickets", content=body, headers=signed(body))
    assert again.json() == {"received": 1, "skipped": 0, "stored": 0}
    (stored,) = store.iter_records()
    assert stored.text == "Erreur de paiement, écrivez à <EMAIL>"
    assert (
        client.post("/ingest/support/nope", content=body, headers=signed(body)).status_code == 404
    )
    bad = {"X-Obsei-Signature-256": "sha256=ü".encode("latin-1")}
    assert client.post("/ingest/support/tickets", content=body, headers=bad).status_code == 401  # type: ignore[arg-type]


def test_mcp_requires_bearer_token(client: TestClient) -> None:
    assert client.post("/mcp", json={}).status_code == 401


def test_ingest_is_atomic_per_request(client: TestClient, store: Store) -> None:
    bad = json.dumps(
        {"tickets": [{"id": "ok", "body": "fine"}, {"id": "x", "body": "late", "at": 1e20}]}
    ).encode()
    rejected = client.post("/ingest/support/tickets", content=bad, headers=signed(bad))
    assert rejected.status_code == 400
    assert "item 1" in rejected.json()["error"]
    good = json.dumps({"tickets": [{"id": "t2", "body": "Works now"}, {"id": "t3"}]}).encode()
    accepted = client.post("/ingest/support/tickets", content=good, headers=signed(good))
    assert accepted.json() == {"received": 2, "skipped": 1, "stored": 1}
    assert [r.source.native_id for r in store.iter_records()] == ["t2"]


def test_every_route_rejects_unknown_hosts(store: Store, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HOOK_SECRET", SECRET)
    cfg = config()
    local = TestClient(create_app(cfg, build_context(cfg), store, token=None), base_url=LOCAL)
    assert local.get("/api/snapshot").status_code == 200
    assert local.get("/healthz", headers={"Host": "localhost:8765"}).status_code == 200
    assert local.get("/healthz", headers={"Host": "[::1]:8765"}).status_code == 200
    for path in ("/api/snapshot", "/healthz", "/studio/", "/mcp"):
        rebound = local.get(path, headers={"Host": "attacker.example:8765"})
        assert rebound.status_code == 421, path
    cross_site = local.post(
        "/api/ask", json={"question": "x"}, headers={"Origin": "https://attacker.example"}
    )
    assert cross_site.status_code == 421
    assert local.get("/healthz", headers={"Origin": "null"}).status_code == 421

    cfg.access.allowed_hosts = ["voc.example.com", "*.corp.example"]
    named = TestClient(create_app(cfg, build_context(cfg), store, token=None), base_url=LOCAL)
    for host in ("voc.example.com", "obsei.corp.example:443"):
        assert named.get("/healthz", headers={"Host": host}).status_code == 200
    assert named.get("/healthz", headers={"Host": "corp.example.evil"}).status_code == 421


def test_bind_address_is_an_allowed_host(store: Store, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HOOK_SECRET", SECRET)
    cfg = config()
    app = create_app(cfg, build_context(cfg), store, token=API_TOKEN, host="10.1.2.3")
    client = TestClient(app, base_url="http://10.1.2.3:8765")
    assert client.get("/healthz").status_code == 200
    assert client.get("/healthz", headers={"Host": "rebound.example"}).status_code == 421
    everywhere = TestClient(
        create_app(cfg, build_context(cfg), store, token=API_TOKEN, host="0.0.0.0")  # noqa: S104
    )
    assert everywhere.get("/healthz").status_code == 200
    assert HostAllowlist("fd00::1", []).allows("[fd00::1]:8765")
