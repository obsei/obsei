import json
import os
import sqlite3
from collections.abc import Callable, Iterator, Mapping
from contextlib import contextmanager
from datetime import UTC, datetime
from email.message import EmailMessage
from pathlib import Path

import httpx
import pytest
import sqlalchemy as sa

from obsei import Enrichment, Record, SourceRef
from obsei.core.context import Context
from obsei.core.protocols import Sink, Source
from obsei.core.registry import Registry
from obsei.llm import EgressPolicy
from obsei.mcp_server import create_server
from obsei.sinks import register as register_sinks
from obsei.sources import register as register_sources
from obsei.sources.imap import ImapSource
from obsei.sources.mcp_client import McpClientSource
from obsei.store import Store

Handler = Callable[[httpx.Request], httpx.Response]
SALT = b"0123456789abcdef-t"


def context(handler: Handler | None = None) -> Context:
    transport = httpx.MockTransport(handler or (lambda _: httpx.Response(500)))
    return Context(
        http=httpx.Client(transport=transport), salt=SALT, egress=EgressPolicy(mode="hybrid")
    )


def source(name: str, config: Mapping[str, object], handler: Handler | None = None) -> Source:
    registry = Registry()
    register_sources(registry)
    return registry.source(name).create(json.loads(json.dumps(config)), context(handler))


def sink(name: str, config: Mapping[str, object], handler: Handler | None = None) -> Sink:
    registry = Registry()
    register_sinks(registry)
    return registry.sink(name).create(json.loads(json.dumps(config)), context(handler))


def records(
    src: Source, cursor: dict[str, str | int | float | bool | None] | None = None
) -> list[Record]:
    return [r for r, _ in src.fetch(cursor)]


def bug(native_id: str, text: str) -> Record:
    return Record(
        source=SourceRef(type="zendesk", native_id=native_id),
        text=text,
        created_at=datetime(2026, 9, 1, tzinfo=UTC),
        rating=1,
        enrichments={"classify": Enrichment(value={"intent": "bug"})},
    )


def test_sql_source_incremental(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    db = tmp_path / "crm.sqlite"
    with sqlite3.connect(db) as con:
        con.execute("CREATE TABLE nps (id INTEGER, comment TEXT, score INTEGER, updated_at TEXT)")
        con.executemany(
            "INSERT INTO nps VALUES (?, ?, ?, ?)",
            [
                (1, "Muito caro", 3, "2026-09-01T00:00:00+00:00"),
                (2, "", 9, "2026-09-02T00:00:00+00:00"),
                (3, "Excellent support", 10, "2026-09-03T00:00:00+00:00"),
            ],
        )
    monkeypatch.setenv("CRM_URL", f"sqlite:///{db}")
    config = {
        "url_env": "CRM_URL",
        "query": "SELECT * FROM nps WHERE updated_at > :since ORDER BY updated_at",
        "fields": {"text": "comment", "rating": "score", "created_at": "updated_at"},
    }
    src = source("sql", config)
    pairs = list(src.fetch(None))
    assert [r.text for r, _ in pairs] == ["Muito caro", "Excellent support"]
    assert pairs[-1][1] == {"since": "2026-09-03T00:00:00+00:00"}
    assert records(src, {"since": "2026-09-02T00:00:00+00:00"})[0].rating == 10.0


def test_sql_source_rejects_writes(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CRM_URL", "sqlite://")
    with pytest.raises(RuntimeError, match="SELECT"):
        source("sql", {"url_env": "CRM_URL", "query": "DELETE FROM nps"})


def test_filedrop_ingests_new_and_modified_files(tmp_path: Path) -> None:
    (tmp_path / "a.csv").write_text("id,text\n1,Lento\n", encoding="utf-8")
    (tmp_path / "b.json").write_text(
        json.dumps({"rows": [{"id": "x", "text": "遅い"}]}), encoding="utf-8"
    )
    src = source("filedrop", {"directory": str(tmp_path), "items_path": "rows"})
    pairs = list(src.fetch(None))
    assert sorted(r.text for r, _ in pairs) == ["Lento", "遅い"]
    assert all(r.source.type == "filedrop" for r, _ in pairs)
    cursor = pairs[-1][1]
    assert records(src, cursor) == []
    (tmp_path / "a.csv").write_text("id,text\n1,Lento\n2,Caro\n", encoding="utf-8")
    os.utime(tmp_path / "a.csv", (2_000_000_000, 2_000_000_000))
    assert [r.text for r in records(src, cursor)] == ["Lento", "Caro"]


class FakeImap:
    def __init__(self, host: str, port: int) -> None:
        message = EmailMessage()
        message["From"] = "Kim <kim@example.kr>"
        message["Subject"] = "앱이 느려요"
        message["Date"] = "Tue, 01 Sep 2026 10:00:00 +0900"
        message["Message-ID"] = "<m1@example.kr>"
        message.set_content("로그인이 너무 느립니다. 010-1234-5678")
        self.raw = message.as_bytes()

    def login(self, user: str, password: str) -> None:
        assert (user, password) == ("u", "p")

    def select(self, folder: str, readonly: bool) -> None:
        assert readonly

    def uid(self, command: str, *args: str) -> tuple[str, list[object]]:
        if command == "search":
            return "OK", [b"7"]
        return "OK", [(b"7 (RFC822)", self.raw)]

    def logout(self) -> None:
        pass


def test_imap_reads_messages(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("IMAP_USERNAME", "u")
    monkeypatch.setenv("IMAP_PASSWORD", "p")
    monkeypatch.setattr(ImapSource, "connect", FakeImap)
    pairs = list(source("imap", {"host": "imap.example.kr"}).fetch(None))
    ((record, cursor),) = pairs
    assert record.text.startswith("앱이 느려요\n\n로그인이")
    assert record.author is not None
    assert cursor == {"uid": 7}


def test_zendesk_incremental_cursor(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ZENDESK_EMAIL", "a@b.c")
    monkeypatch.setenv("ZENDESK_API_TOKEN", "t")

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["Authorization"].startswith("Basic ")
        if request.url.params.get("cursor") == "c2":
            return httpx.Response(
                200, json={"tickets": [], "after_cursor": "c3", "end_of_stream": True}
            )
        ticket = {
            "id": 42,
            "subject": "Zahlung fehlgeschlagen",
            "description": "Karte abgelehnt",
            "created_at": "2026-09-01T00:00:00Z",
            "requester_id": 9,
            "status": "open",
            "via": {"channel": "email"},
            "tags": ["billing"],
        }
        return httpx.Response(
            200, json={"tickets": [ticket], "after_cursor": "c2", "end_of_stream": False}
        )

    pairs = list(source("zendesk", {"subdomain": "acme"}, handler).fetch(None))
    assert pairs[0][0].context == {"status": "open", "channel": "email", "tags": "billing"}
    assert pairs[0][1] == {"cursor": "c2"}


def test_freshdesk_and_intercom(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FRESHDESK_API_KEY", "k")
    monkeypatch.setenv("INTERCOM_TOKEN", "t")

    def freshdesk(request: httpx.Request) -> httpx.Response:
        if request.url.params["page"] != "1":
            return httpx.Response(200, json=[])
        ticket = {
            "id": 5,
            "subject": "Retard",
            "description_text": "Livraison en retard",
            "created_at": "2026-09-01T00:00:00Z",
            "updated_at": "2026-09-02T00:00:00Z",
        }
        return httpx.Response(200, json=[ticket])

    ((fd, cursor),) = list(source("freshdesk", {"domain": "acme"}, freshdesk).fetch(None))
    assert fd.text == "Retard\n\nLivraison en retard"
    assert cursor == {"since": "2026-09-02T00:00:00Z"}

    def intercom(request: httpx.Request) -> httpx.Response:
        assert request.url.host == "api.eu.intercom.io"
        conversation = {
            "id": "c1",
            "created_at": 1788000000,
            "updated_at": 1788000500,
            "source": {"body": "<p>Can't export</p>", "author": {"id": "u1"}},
            "conversation_rating": {"rating": 2},
        }
        return httpx.Response(200, json={"conversations": [conversation], "pages": {}})

    ((ic, cursor),) = list(source("intercom", {"region": "eu"}, intercom).fetch(None))
    assert ic.text == "Can't export"
    assert ic.rating == 2.0
    assert cursor == {"updated_at": 1788000500}


def test_mcp_client_source_pulls_from_another_server() -> None:
    upstream = Store(allow_unencrypted=True)
    upstream.upsert([bug("1", "Checkout freezes")])

    @contextmanager
    def opener() -> Iterator[Store]:
        yield upstream

    src = source(
        "mcp",
        {
            "command": ["unused"],
            "tool": "search_feedback",
            "items_path": "items",
            "arguments": {"limit": 5},
            "fields": {"created_at": "created_at"},
        },
    )
    assert isinstance(src, McpClientSource)
    src.server = create_server(opener)
    (record,) = records(src)
    assert record.text == "Checkout freezes"
    assert record.source.type == "mcp"


def test_jira_sink_creates_once(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JIRA_EMAIL", "a@b.c")
    monkeypatch.setenv("JIRA_API_TOKEN", "t")
    created: list[dict[str, object]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/search/jql"):
            return httpx.Response(200, json={"issues": [{"key": "X-1"}] if created else []})
        created.append(json.loads(request.content))
        return httpx.Response(201, json={"key": "X-1"})

    jira = sink("jira", {"base_url": "https://acme.atlassian.net", "project_key": "APP"}, handler)
    assert jira.send([bug("1", "Crash on pay")]).sent == 1
    assert jira.send([bug("1", "Crash on pay")]).skipped == 1
    fields = created[0]["fields"]
    assert isinstance(fields, dict)
    assert fields["summary"] == "[bug] Crash on pay"
    assert fields["description"]["type"] == "doc"


def test_linear_sink(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LINEAR_API_KEY", "k")
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        query = json.loads(request.content)["query"]
        calls.append(query.split("(")[0])
        if query.startswith("query"):
            return httpx.Response(200, json={"data": {"issues": {"nodes": []}}})
        return httpx.Response(200, json={"data": {"issueCreate": {"success": True}}})

    assert sink("linear", {"team_id": "T"}, handler).send([bug("1", "Crash")]).sent == 1
    assert calls == ["query", "mutation"]


def test_sql_sink_upserts(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DWH_URL", f"sqlite:///{tmp_path / 'dwh.sqlite'}")
    warehouse = sink("sql", {"url_env": "DWH_URL"})
    warehouse.send([bug("1", "a"), bug("2", "b")])
    warehouse.send([bug("1", "a edited")])
    engine = sa.create_engine(f"sqlite:///{tmp_path / 'dwh.sqlite'}")
    with engine.connect() as con:
        rows = con.execute(
            sa.text("SELECT id, text, author_pseudonym FROM obsei_feedback ORDER BY text")
        ).all()
    assert [(r[1], r[2]) for r in rows] == [("a edited", None), ("b", None)]
