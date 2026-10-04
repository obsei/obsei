import json

import pytest
from starlette.testclient import TestClient

from obsei.access import AccessConfig, AccessError, Authenticator, required_role
from obsei.config import ObseiConfig
from obsei.core.context import Context
from obsei.demo import demo_records
from obsei.llm.embed import HashingEmbedder
from obsei.serve import create_app
from obsei.store import Store
from obsei.themes import ThemesConfig, update_themes

VIEWER, ANALYST, ADMIN, PROXY = (
    "viewer-token-0123456789",
    "analyst-token-0123456789",
    "admin-token-0123456789",
    "proxy-secret-0123456789",
)
LOCAL = "http://127.0.0.1:8765"


def config() -> ObseiConfig:
    return ObseiConfig.model_validate(
        {
            "access": {
                "users": [
                    {"name": "support-leads", "token_env": "T_VIEWER", "role": "viewer"},
                    {"name": "voc-team", "token_env": "T_ANALYST", "role": "analyst"},
                ],
                "trusted_proxy": {
                    "secret_env": "T_PROXY",
                    "roles": {"analyst": ["voc"], "admin": ["platform"]},
                    "default_role": "viewer",
                },
            },
            "pipelines": [
                {"name": "p", "sources": [{"key": "s", "type": "csv", "config": {"path": "x.csv"}}]}
            ],
        }
    )


@pytest.fixture
def store() -> Store:
    s = Store(allow_unencrypted=True)
    s.upsert(demo_records())
    update_themes(s, HashingEmbedder(), ThemesConfig(k_anonymity=5))
    return s


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch, store: Store) -> TestClient:
    for env, value in (("T_VIEWER", VIEWER), ("T_ANALYST", ANALYST), ("T_PROXY", PROXY)):
        monkeypatch.setenv(env, value)
    return TestClient(create_app(config(), Context(), store, token=ADMIN), base_url=LOCAL)


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_required_roles() -> None:
    assert required_role("/studio/") is None
    assert required_role("/ingest/p/s") is None
    assert required_role("/api/snapshot") == "viewer"
    assert required_role("/api/themes/thm_1") == "analyst"
    assert required_role("/mcp") == "analyst"
    assert required_role("/api/runs") == "admin"
    assert required_role("/anything-else") == "admin"


def test_roles_limit_what_each_token_sees(client: TestClient, store: Store) -> None:
    theme = client.get("/api/snapshot", headers=bearer(VIEWER)).json()["themes"][0]["id"]
    assert client.get(f"/api/themes/{theme}", headers=bearer(VIEWER)).status_code == 403
    assert client.get(f"/api/themes/{theme}", headers=bearer(ANALYST)).status_code == 200
    assert client.get("/api/runs", headers=bearer(ANALYST)).status_code == 403
    assert client.get("/api/runs", headers=bearer(ADMIN)).status_code == 200
    assert client.get("/api/snapshot", headers=bearer("wrong-token-0123456789")).status_code == 401
    log = [json.loads(detail) for _, action, detail in store.audit_log() if action == "access"]
    assert {"user": "voc-team", "role": "analyst", "path": f"/api/themes/{theme}"} in log
    assert all(entry["user"] != "support-leads" for entry in log)


def test_trusted_proxy_maps_groups_to_roles(client: TestClient) -> None:
    theme = client.get("/api/snapshot", headers=bearer(ADMIN)).json()["themes"][0]["id"]
    sso = {"X-Obsei-Proxy-Secret": PROXY, "X-Forwarded-Email": "ana@example.com"}
    assert client.get("/api/snapshot", headers=sso).status_code == 200
    assert client.get(f"/api/themes/{theme}", headers=sso).status_code == 403
    analyst = {**sso, "X-Forwarded-Groups": "everyone, voc"}
    assert client.get(f"/api/themes/{theme}", headers=analyst).status_code == 200
    forged = {**analyst, "X-Obsei-Proxy-Secret": "not-the-secret-000000"}
    assert client.get("/api/snapshot", headers=forged).status_code == 401
    assert client.get("/studio/").status_code == 200


def test_tokens_must_be_set_and_long(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("T_VIEWER", "short")
    with pytest.raises(AccessError, match="T_VIEWER"):
        Authenticator(config().access, None)
    assert not Authenticator(AccessConfig(), None).enabled


def test_non_ascii_credentials_are_unauthorized_not_errors(client: TestClient) -> None:
    for header in (
        {"Authorization": "Bearer tökén-0123456789"},
        {"x-obsei-proxy-secret": "sécret-0123456789", "x-forwarded-email": "a@b.co"},
    ):
        encoded = {k: v.encode("latin-1") for k, v in header.items()}
        response = client.get("/api/snapshot", headers=encoded)  # type: ignore[arg-type]
        assert response.status_code == 401


def test_admin_token_must_be_long() -> None:
    with pytest.raises(AccessError, match="OBSEI_API_TOKEN"):
        Authenticator(AccessConfig(), "short")
    assert Authenticator(AccessConfig(), "a" * 16).enabled
