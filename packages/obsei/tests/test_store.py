from datetime import UTC, datetime, timedelta
from pathlib import Path

import duckdb
import pytest

from obsei import Author, Enrichment, Record, SourceRef
from obsei.store import (
    EncryptionUnavailableError,
    Store,
    StoreError,
    UpsertResult,
    load_db_key,
)

KEY = "correct-horse-battery-staple"
T0 = datetime(2026, 9, 1, tzinfo=UTC)


def rec(
    native_id: str, text: str = "slow checkout", *, source: str = "csv", days: int = 0
) -> Record:
    return Record(
        source=SourceRef(type=source, native_id=native_id),
        text=text,
        created_at=T0 + timedelta(days=days),
    )


@pytest.fixture
def store() -> Store:
    return Store(allow_unencrypted=True)


def _crypto_available() -> bool:
    try:
        con = duckdb.connect()
        con.execute("INSTALL httpfs")
        con.execute("LOAD httpfs")
    except duckdb.Error:
        return False
    return True


needs_crypto = pytest.mark.skipif(
    not _crypto_available(), reason="DuckDB httpfs extension (OpenSSL) not available"
)


def test_requires_key_or_explicit_opt_out() -> None:
    with pytest.raises(StoreError, match="encryption key is required"):
        Store()
    with pytest.raises(StoreError, match="at least"):
        Store(encryption_key="short")


def test_upsert_is_idempotent(store: Store) -> None:
    records = [rec("1"), rec("2")]
    assert store.upsert(records) == UpsertResult(inserted=2)
    assert store.upsert(records) == UpsertResult(unchanged=2)
    assert store.count() == 2


def test_refetch_with_new_fetched_at_is_unchanged(store: Store) -> None:
    store.upsert([rec("1")])
    refetched = rec("1").model_copy(update={"fetched_at": datetime.now(UTC) + timedelta(hours=1)})
    assert store.upsert([refetched]) == UpsertResult(unchanged=1)


def test_changed_text_or_enrichment_updates(store: Store) -> None:
    store.upsert([rec("1")])
    edited = rec("1", text="checkout is fast now")
    assert store.upsert([edited]) == UpsertResult(updated=1)
    enriched = edited.with_enrichment("sentiment", Enrichment(value="positive", at=T0))
    assert store.upsert([enriched]) == UpsertResult(updated=1)
    stored = store.get(edited.id)
    assert stored is not None
    assert stored.text == "checkout is fast now"
    assert stored.enrichments["sentiment"].value == "positive"


def test_duplicate_ids_in_one_batch_keep_last(store: Store) -> None:
    assert store.upsert([rec("1", "a"), rec("1", "b")]) == UpsertResult(inserted=1)
    stored = store.get(rec("1").id)
    assert stored is not None
    assert stored.text == "b"


def test_get_round_trips_and_missing_is_none(store: Store) -> None:
    record = rec("1")
    store.upsert([record])
    assert store.get(record.id) == record
    assert store.get("rec_" + "0" * 32) is None


def test_iter_records_filters_and_orders(store: Store) -> None:
    store.upsert(
        [
            rec("a", days=2),
            rec("b", days=0),
            rec("c", days=1, source="appstore"),
            rec("d", days=3, source="appstore"),
        ]
    )
    assert [r.source.native_id for r in store.iter_records()] == ["b", "c", "a", "d"]
    assert [r.source.native_id for r in store.iter_records(source_type="appstore")] == ["c", "d"]
    since = T0 + timedelta(days=2)
    assert [r.source.native_id for r in store.iter_records(since=since)] == ["a", "d"]
    assert [r.source.native_id for r in store.iter_records(limit=1)] == ["b"]
    assert store.count(source_type="appstore") == 2
    with pytest.raises(ValueError, match="timezone-aware"):
        list(store.iter_records(since=datetime(2026, 1, 1)))


def test_cursors(store: Store) -> None:
    assert store.get_cursor("daily", "appstore") is None
    store.set_cursor("daily", "appstore", {"page": 2, "token": "abc"})
    store.set_cursor("daily", "appstore", {"page": 3, "token": None})
    assert store.get_cursor("daily", "appstore") == {"page": 3, "token": None}
    assert store.get_cursor("other", "appstore") is None


def test_enrichment_retries_are_tracked_and_erased(store: Store) -> None:
    store.upsert([rec("1"), rec("2", days=1), rec("3", source="rss")])
    ids = {r.source.native_id: r.id for r in store.iter_records()}
    store.track_retries("daily", "csv", done=[], failed=[ids["1"], ids["2"], ids["2"]])
    assert [r.id for r in store.retry_records("daily", "csv", 10)] == [ids["1"], ids["2"]]
    assert store.retry_records("daily", "other", 10) == []
    store.track_retries("daily", "csv", done=[ids["1"]], failed=[])
    assert [r.id for r in store.retry_records("daily", "csv", 10)] == [ids["2"]]
    store.delete(source_type="csv")
    assert store.retry_records("daily", "csv", 10) == []
    assert store._con.execute("SELECT count(*) FROM enrichment_retries").fetchone() == (0,)


def test_file_store_persists_and_reopens_read_only(tmp_path: Path) -> None:
    path = tmp_path / "obsei.duckdb"
    record = rec("1")
    with Store(path, allow_unencrypted=True) as store:
        store.upsert([record])
        assert store.schema_version() == 4
    with Store(path, allow_unencrypted=True, read_only=True) as store:
        assert store.get(record.id) == record
        with pytest.raises(duckdb.Error):
            store.upsert([rec("2")])


def test_newer_schema_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "obsei.duckdb"
    con = duckdb.connect(str(path))
    con.execute(
        "CREATE TABLE schema_migrations (version INTEGER PRIMARY KEY, applied_at TIMESTAMPTZ)"
    )
    con.execute("INSERT INTO schema_migrations VALUES (99, now())")
    con.close()
    with pytest.raises(StoreError, match="newer"):
        Store(path, allow_unencrypted=True)


def test_load_db_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OBSEI_DB_KEY", raising=False)
    assert load_db_key() is None
    monkeypatch.setenv("OBSEI_DB_KEY", "short")
    with pytest.raises(StoreError):
        load_db_key()
    monkeypatch.setenv("OBSEI_DB_KEY", KEY)
    assert load_db_key() == KEY


@pytest.mark.skipif(_crypto_available(), reason="only meaningful where httpfs is missing")
def test_clear_error_when_crypto_missing(tmp_path: Path) -> None:
    with pytest.raises(EncryptionUnavailableError, match="httpfs"):
        Store(tmp_path / "enc.duckdb", encryption_key=KEY, install_extensions=False)


@needs_crypto
def test_encrypted_store_hides_plaintext_and_needs_the_key(tmp_path: Path) -> None:
    path = tmp_path / "enc.duckdb"
    sensitive_text = "customer says the refund never arrived"
    with Store(path, encryption_key=KEY) as store:
        store.upsert([rec("1", sensitive_text)])
    assert sensitive_text.encode() not in path.read_bytes()

    with pytest.raises(StoreError):
        Store(path, encryption_key="wrong-key-wrong-key")
    with pytest.raises(StoreError):
        Store(path, allow_unencrypted=True)
    with Store(path, encryption_key=KEY, read_only=True) as store:
        stored = store.get(rec("1").id)
        assert stored is not None
        assert stored.text == sensitive_text


def test_delete_by_author_source_and_age(store: Store) -> None:
    author = Author(pseudonym="psn_" + "a" * 32)
    store.upsert(
        [
            rec("1").model_copy(update={"author": author}),
            rec("2", days=10),
            rec("3", source="appstore", days=20),
        ]
    )
    assert [r.source.native_id for r in store.iter_records(author_pseudonym=author.pseudonym)] == [
        "1"
    ]
    assert store.delete(author_pseudonym=author.pseudonym) == 1
    assert store.delete(before=T0 + timedelta(days=15)) == 1
    assert store.delete(source_type="appstore") == 1
    assert store.count() == 0
    with pytest.raises(StoreError, match="filter"):
        store.delete()
