import hashlib
import hmac
import json

import pytest
from starlette.testclient import TestClient

from obsei.config import ObseiConfig, build_context
from obsei.serve import create_app
from obsei.store import Store

SECRET = "hook-secret-0123456789"


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
    app = create_app(cfg, build_context(cfg), store, token="api-token")
    return TestClient(app)


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
