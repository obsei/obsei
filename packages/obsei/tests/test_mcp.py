import json
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime

import anyio
import pytest

from obsei import Author, Enrichment, Record, SourceRef, __version__
from obsei.mcp_server import create_server
from obsei.store import Query, Store


def record(native_id: str, text: str, day: int, intent: str, rating: float, lang: str) -> Record:  # noqa: PLR0917
    return Record(
        source=SourceRef(type="appstore" if day % 2 else "playstore", native_id=native_id),
        text=text,
        created_at=datetime(2026, 9, day, tzinfo=UTC),
        rating=rating,
        lang=lang,
        author=Author(pseudonym="psn_" + "a" * 32),
        enrichments={
            "classify": Enrichment(
                value={"intent": intent, "sentiment": "negative" if rating < 3 else "positive"}
            )
        },
    )


@pytest.fixture
def store() -> Store:
    s = Store(allow_unencrypted=True)
    s.upsert(
        [
            record("1", "Login CRASH on iOS 19", 1, "bug", 1, "en"),
            record("2", "La app se cierra al iniciar sesión (crash)", 2, "bug", 2, "es"),
            record("3", "Великолепно", 3, "praise", 5, "ru"),
            record("4", "ログインできない", 4, "bug", 1, "ja"),
        ]
    )
    return s


def test_store_search_filters(store: Store) -> None:
    assert [r.source.native_id for r in store.search(Query(text="crash"))] == ["2", "1"]
    assert [r.lang for r in store.search(Query(intent="bug", max_rating=1))] == ["ja", "en"]
    assert store.search(Query(text="ВЕЛИКОЛЕПНО"))[0].lang == "ru"
    assert (
        store.search(Query(since=datetime(2026, 9, 4, tzinfo=UTC)), limit=5)[0].text
        == "ログインできない"
    )


def test_store_stats(store: Store) -> None:
    by_intent = {row.key: (row.count, row.avg_rating) for row in store.stats(Query(), "intent")}
    assert by_intent == {"bug": (3, pytest.approx(4 / 3)), "praise": (1, 5.0)}
    days = [row.key for row in store.stats(Query(), "day")]
    assert days == ["2026-09-01", "2026-09-02", "2026-09-03", "2026-09-04"]
    assert [row.key for row in store.stats(Query(lang="es"), "source")] == ["playstore"]


def call(store: Store, tool: str, arguments: dict[str, object]) -> dict[str, object]:
    @contextmanager
    def opener() -> Iterator[Store]:
        yield store

    server = create_server(opener)

    async def go() -> dict[str, object]:
        result = await server.call_tool(tool, arguments)
        structured = getattr(result, "structured_content", None)
        assert isinstance(structured, dict)
        return structured

    return anyio.run(go)


def test_mcp_search_returns_evidence_without_authors(store: Store) -> None:
    result = call(store, "search_feedback", {"text": "crash", "limit": 5})
    assert result["count"] == 2
    payload = json.dumps(result, ensure_ascii=False)
    assert "psn_" not in payload
    assert "author" not in payload
    items = result["items"]
    assert isinstance(items, list)
    assert items[0]["labels"]["intent"] == "bug"


def test_mcp_stats_and_get(store: Store) -> None:
    stats = call(store, "feedback_stats", {"group_by": "sentiment"})
    assert stats["total"] == 4
    record_id = store.search(Query(lang="ja"))[0].id
    found = call(store, "get_feedback", {"id": record_id})
    assert found["items"] == [call(store, "search_feedback", {"lang": "ja"})["items"][0]]  # type: ignore[index]


def test_mcp_lists_read_only_tools(store: Store) -> None:
    @contextmanager
    def opener() -> Iterator[Store]:
        yield store

    tools = anyio.run(create_server(opener).list_tools)
    assert {t.name for t in tools} == {
        "search_feedback",
        "feedback_stats",
        "get_feedback",
        "list_themes",
    }
    assert all(t.annotations and t.annotations.read_only_hint for t in tools)


def test_server_reports_pep440_version(store: Store) -> None:
    @contextmanager
    def opener() -> Iterator[Store]:
        yield store

    assert create_server(opener).version == __version__
    assert "-" not in __version__
