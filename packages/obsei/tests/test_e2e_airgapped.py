"""Phase gate: a full pipeline with a local model and local sinks, with no outside network."""

import json
import socket
import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest
from typer.testing import CliRunner

from obsei.cli import app
from obsei.store import Store

runner = CliRunner()


class LocalServices(BaseHTTPRequestHandler):
    hooks: list[dict[str, object]] = []  # noqa: RUF012
    prompts: list[str] = []  # noqa: RUF012

    def log_message(self, format: str, *args: object) -> None:
        pass

    def _reply(self, payload: object) -> None:
        body = json.dumps(payload).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self) -> None:
        data = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        if self.path == "/v1/chat/completions":
            feedback = data["messages"][-1]["content"]
            self.prompts.append(feedback)
            negative = any(w in feedback for w in ("crash", "langsam", "reembolso", "connecter"))
            result: dict[str, object] = {
                "sentiment": "negative" if negative else "positive",
                "intent": "bug" if negative else "praise",
                "language": "und",
                "confidence": 0.9,
                "fields": {},
            }
            self._reply({"choices": [{"message": {"content": json.dumps(result)}}]})
        else:
            self.hooks.append(data)
            self._reply({})


@pytest.fixture
def services() -> Iterator[str]:
    LocalServices.hooks.clear()
    LocalServices.prompts.clear()
    server = ThreadingHTTPServer(("127.0.0.1", 0), LocalServices)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()


@pytest.fixture
def offline(monkeypatch: pytest.MonkeyPatch) -> None:
    for var in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy"):
        monkeypatch.delenv(var, raising=False)
    for var in ("OBSEI_EGRESS_MODE", "OBSEI_EGRESS_ALLOW", "OBSEI_DB_KEY", "OBSEI_DB"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("OBSEI_PSEUDONYM_SALT", "e2e-salt-0123456789")
    original = socket.socket.connect

    def loopback_only(sock: socket.socket, address: object) -> None:
        host = address[0] if isinstance(address, tuple) else str(address)
        if host not in ("127.0.0.1", "::1", "localhost"):
            raise AssertionError(f"unexpected outbound connection to {address!r}")
        original(sock, address)  # type: ignore[arg-type]

    monkeypatch.setattr(socket.socket, "connect", loopback_only)


CSV = """id,date,rating,lang,user,comment
1,2026-09-01,1,en,alice@example.com,App crash on login. Call me at +1 415 555 0134
2,2026-09-01,5,es,bea,Me encanta. Mi correo es bea@example.es
3,2026-09-02,2,de,chris,Sync ist langsam. IBAN DE89 3704 0044 0532 0130 00
4,2026-09-03,1,pt,dani,Quero reembolso. CPF 529.982.247-25
5,2026-09-04,2,fr,eve,Impossible de me connecter
6,2026-09-05,5,hi,farah,बहुत अच्छा ऐप। आधार २३४१ २३४१ २३४६
"""


def write_project(tmp_path: Path, llm_url: str, hook_url: str) -> Path:
    (tmp_path / "feedback.csv").write_text(CSV, encoding="utf-8")
    config = {
        "store": {"path": str(tmp_path / "obsei.duckdb"), "unencrypted": True},
        "llms": {"local": {"base_url": llm_url, "model": "local-model"}},
        "pipelines": [
            {
                "name": "feedback",
                "sources": [
                    {
                        "key": "survey",
                        "type": "csv",
                        "config": {
                            "path": str(tmp_path / "feedback.csv"),
                            "fields": {
                                "text": "comment",
                                "created_at": "date",
                                "rating": "rating",
                                "lang": "lang",
                                "author": "user",
                            },
                        },
                    }
                ],
                "enrichers": [{"type": "classify", "config": {"llm": "local"}}],
                "sinks": [
                    {"type": "webhook", "config": {"url": hook_url}},
                    {"type": "parquet", "config": {"directory": str(tmp_path / "exports")}},
                ],
            }
        ],
    }
    path = tmp_path / "obsei.yaml"
    path.write_text(json.dumps(config), encoding="utf-8")
    return path


@pytest.mark.usefixtures("offline")
def test_air_gapped_pipeline(tmp_path: Path, services: str) -> None:
    config = write_project(tmp_path, f"{services}/v1", f"{services}/hook")

    first = runner.invoke(app, ["run", "--config", str(config)])
    assert first.exit_code == 0, first.output
    assert "fetched 6, stored 6, enriched 6, sent webhook=6, parquet=6" in first.output

    leaked = ("alice@", "bea@example", "415 555", "DE89", "529.982", "२३४१", "alice", "farah")
    sent = json.dumps(LocalServices.hooks, ensure_ascii=False)
    assert not any(secret in sent for secret in leaked)
    assert not any(secret in p for p in LocalServices.prompts for secret in leaked)
    records = LocalServices.hooks[0]["records"]
    assert isinstance(records, list)
    assert records[0]["enrichments"]["classify"]["value"]["intent"] == "bug"
    assert "<PHONE>" in records[0]["text"]

    with Store(tmp_path / "obsei.duckdb", allow_unencrypted=True, read_only=True) as store:
        assert store.count() == 6
        stored = list(store.iter_records())
    assert all(r.author is not None and r.author.pseudonym.startswith("psn_") for r in stored)
    assert not any(secret in r.model_dump_json() for r in stored for secret in leaked)
    assert len(list((tmp_path / "exports").glob("*.parquet"))) == 1

    second = runner.invoke(app, ["run", "--config", str(config)])
    assert second.exit_code == 0, second.output
    assert "fetched 6, stored 0, enriched 0, sent none" in second.output
    assert len(LocalServices.hooks) == 1


@pytest.mark.usefixtures("offline")
def test_public_model_endpoint_is_refused(tmp_path: Path, services: str) -> None:
    config = write_project(tmp_path, "https://api.openai.com/v1", f"{services}/hook")
    result = runner.invoke(app, ["run", "--config", str(config)])
    assert result.exit_code == 1
    assert "feedback: failed" in result.output
    assert "blocked in air_gapped mode" in result.output
    assert LocalServices.hooks == []
