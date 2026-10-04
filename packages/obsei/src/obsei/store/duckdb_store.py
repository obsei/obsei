"""Single-file DuckDB store, encrypted at rest by default. DuckDB allows one writer process."""

from __future__ import annotations

import json
import os
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from types import TracebackType
from typing import Literal, Self, TypeAlias

import duckdb
from pydantic import BaseModel, ConfigDict, Field

from obsei.core.protocols import Cursor
from obsei.core.record import Record
from obsei.store.themes import ThemeQueries

DB_KEY_ENV_VAR = "OBSEI_DB_KEY"
MIN_KEY_LENGTH = 16
_ALIAS = "obsei"

RecordRow: TypeAlias = tuple[str, str, str, datetime, str, str | None, str, str]
InsertRow: TypeAlias = tuple[str, str, str, datetime, str, str | None, str, str, datetime, datetime]
UpdateRow: TypeAlias = tuple[str, str, datetime, str, str | None, str, str, datetime, str]
SqlParam: TypeAlias = str | int | datetime

# Append-only: never edit a released migration.
MIGRATIONS: tuple[str, ...] = (
    """
    CREATE TABLE records (
        id VARCHAR PRIMARY KEY,
        source_type VARCHAR NOT NULL,
        source_instance VARCHAR NOT NULL,
        created_at TIMESTAMPTZ NOT NULL,
        content_hash VARCHAR NOT NULL,
        author_pseudonym VARCHAR,
        purpose VARCHAR NOT NULL,
        data JSON NOT NULL,
        first_seen_at TIMESTAMPTZ NOT NULL,
        updated_at TIMESTAMPTZ NOT NULL
    );
    CREATE INDEX records_source_created ON records (source_type, created_at);
    CREATE TABLE cursors (
        pipeline VARCHAR NOT NULL,
        source VARCHAR NOT NULL,
        cursor JSON NOT NULL,
        updated_at TIMESTAMPTZ NOT NULL,
        PRIMARY KEY (pipeline, source)
    );
    """,
    """
    CREATE TABLE audit_log (
        logged_at TIMESTAMPTZ NOT NULL,
        action VARCHAR NOT NULL,
        detail JSON NOT NULL
    );
    """,
    """
    CREATE TABLE embeddings (
        record_id VARCHAR PRIMARY KEY,
        model VARCHAR NOT NULL,
        content_hash VARCHAR NOT NULL,
        vector FLOAT[] NOT NULL
    );
    CREATE TABLE themes (
        id VARCHAR PRIMARY KEY,
        model VARCHAR NOT NULL,
        label VARCHAR,
        description VARCHAR,
        centroid FLOAT[] NOT NULL,
        size INTEGER NOT NULL,
        created_at TIMESTAMPTZ NOT NULL,
        updated_at TIMESTAMPTZ NOT NULL
    );
    CREATE TABLE record_themes (
        record_id VARCHAR PRIMARY KEY,
        theme_id VARCHAR NOT NULL,
        similarity DOUBLE NOT NULL,
        duplicate_of VARCHAR
    );
    """,
    """
    CREATE TABLE enrichment_retries (
        pipeline VARCHAR NOT NULL,
        source VARCHAR NOT NULL,
        record_id VARCHAR NOT NULL,
        PRIMARY KEY (pipeline, source, record_id)
    );
    """,
)


GroupBy: TypeAlias = Literal[
    "source", "instance", "sentiment", "intent", "lang", "rating", "day", "week", "month"
]
_LABEL = "json_extract_string(data, '$.enrichments.classify.value.{}')"
_GROUPS: dict[GroupBy, str] = {
    "source": "source_type",
    "instance": "source_type || '/' || source_instance",
    "sentiment": _LABEL.format("sentiment"),
    "intent": _LABEL.format("intent"),
    "lang": f"coalesce(json_extract_string(data, '$.lang'), {_LABEL.format('language')})",
    "rating": "CAST(json_extract_string(data, '$.rating') AS DOUBLE)",
    "day": "strftime(date_trunc('day', created_at), '%Y-%m-%d')",
    "week": "strftime(date_trunc('week', created_at), '%Y-%m-%d')",
    "month": "strftime(date_trunc('month', created_at), '%Y-%m')",
}


class Query(BaseModel):
    """Filters for search and stats. Every filter is optional."""

    model_config = ConfigDict(extra="forbid")

    text: str | None = Field(default=None, description="Case-insensitive substring.")
    source: str | None = None
    instance: str | None = None
    since: datetime | None = None
    until: datetime | None = None
    min_rating: float | None = None
    max_rating: float | None = None
    sentiment: str | None = None
    intent: str | None = None
    lang: str | None = None
    theme: str | None = None

    def where(self) -> tuple[str, list[SqlParam | float]]:
        clauses, base = _filters(
            source_type=self.source,
            source_instance=self.instance,
            since=self.since,
            before=self.until,
        )
        params: list[SqlParam | float] = list(base)
        if self.text:
            clauses.append("contains(lower(json_extract_string(data, '$.text')), lower(?))")
            params.append(self.text)
        for op, rating in ((">=", self.min_rating), ("<=", self.max_rating)):
            if rating is not None:
                clauses.append(f"CAST(json_extract_string(data, '$.rating') AS DOUBLE) {op} ?")
                params.append(rating)
        labels: tuple[tuple[GroupBy, str | None], ...] = (
            ("sentiment", self.sentiment),
            ("intent", self.intent),
            ("lang", self.lang),
        )
        for group, value in labels:
            if value is not None:
                clauses.append(f"{_GROUPS[group]} = ?")
                params.append(value)
        if self.theme is not None:
            clauses.append("id IN (SELECT record_id FROM record_themes WHERE theme_id = ?)")
            params.append(self.theme)
        return (" WHERE " + " AND ".join(clauses)) if clauses else "", params


@dataclass(frozen=True)
class StatRow:
    key: str | None
    count: int
    avg_rating: float | None


class StoreError(Exception):
    pass


class EncryptionUnavailableError(StoreError):
    pass


@dataclass(frozen=True)
class UpsertResult:
    inserted: int = 0
    updated: int = 0
    unchanged: int = 0


def load_db_key(env_var: str = DB_KEY_ENV_VAR) -> str | None:
    key = os.environ.get(env_var) or None
    if key is not None and len(key) < MIN_KEY_LENGTH:
        raise StoreError(f"{env_var} must be at least {MIN_KEY_LENGTH} characters")
    return key


def _sql_literal(value: str) -> str:
    if "\x00" in value:
        raise StoreError("value must not contain NUL characters")
    return "'" + value.replace("'", "''") + "'"


def _comparable(record: Record) -> str:
    return record.model_dump_json(exclude={"fetched_at"})


def _content(record: Record) -> str:
    return record.model_dump_json(exclude={"fetched_at", "enrichments"})


def _filters(
    *,
    source_type: str | None = None,
    source_instance: str | None = None,
    author_pseudonym: str | None = None,
    since: datetime | None = None,
    before: datetime | None = None,
) -> tuple[list[str], list[SqlParam]]:
    clauses: list[str] = []
    params: list[SqlParam] = []
    for column, value in (
        ("source_type", source_type),
        ("source_instance", source_instance),
        ("author_pseudonym", author_pseudonym),
    ):
        if value is not None:
            clauses.append(f"{column} = ?")
            params.append(value)
    for op, moment in ((">=", since), ("<", before)):
        if moment is not None:
            if moment.tzinfo is None:
                raise ValueError("timestamps must be timezone-aware")
            clauses.append(f"created_at {op} ?")
            params.append(moment)
    return clauses, params


class Store(ThemeQueries):
    """Without ``encryption_key`` you must pass ``allow_unencrypted=True`` (e.g. encrypted disk)."""

    def __init__(
        self,
        path: str | Path = ":memory:",
        *,
        encryption_key: str | None = None,
        allow_unencrypted: bool = False,
        read_only: bool = False,
        install_extensions: bool = True,
    ) -> None:
        if encryption_key is None and not allow_unencrypted:
            raise StoreError(
                f"an encryption key is required: set {DB_KEY_ENV_VAR} or pass "
                "allow_unencrypted=True (only when the disk is encrypted)"
            )
        if encryption_key is not None and len(encryption_key) < MIN_KEY_LENGTH:
            raise StoreError(f"encryption key must be at least {MIN_KEY_LENGTH} characters")
        self.path = str(path)
        self.read_only = read_only
        self.encrypted = encryption_key is not None
        self._con = duckdb.connect()
        try:
            if encryption_key is not None and not read_only:
                self._load_crypto(install_extensions)
            options = []
            if encryption_key is not None:
                options.append(f"ENCRYPTION_KEY {_sql_literal(encryption_key)}")
            if read_only:
                options.append("READ_ONLY")
            opts = f" ({', '.join(options)})" if options else ""
            try:
                self._con.execute(f"ATTACH {_sql_literal(self.path)} AS {_ALIAS}{opts}")
            except duckdb.Error as exc:
                raise StoreError(f"cannot open store at {self.path}: {exc}") from None
            self._con.execute(f"USE {_ALIAS}")
            self._migrate()
        except BaseException:
            self._con.close()
            raise

    def close(self) -> None:
        self._con.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close()

    def _load_crypto(self, install: bool) -> None:
        try:
            if install:
                self._con.execute("INSTALL httpfs")
            self._con.execute("LOAD httpfs")
        except duckdb.Error as exc:
            raise EncryptionUnavailableError(
                "writing an encrypted store needs DuckDB's httpfs extension (OpenSSL), which "
                f"could not be loaded: {exc}. Install it once with network access "
                "(python -c \"import duckdb; duckdb.connect().execute('INSTALL httpfs')\"), "
                "use the obsei container image, or rely on disk encryption with "
                "allow_unencrypted=True."
            ) from None

    def _migrate(self) -> None:
        if not self.read_only:
            self._con.execute(
                "CREATE TABLE IF NOT EXISTS schema_migrations "
                "(version INTEGER PRIMARY KEY, applied_at TIMESTAMPTZ NOT NULL)"
            )
        current = self.schema_version()
        if current > len(MIGRATIONS):
            raise StoreError(
                f"store schema version {current} is newer than this obsei supports "
                f"({len(MIGRATIONS)}); upgrade obsei"
            )
        if current == len(MIGRATIONS):
            return
        if self.read_only:
            raise StoreError("store needs a schema migration; open it once read-write")
        for version in range(current + 1, len(MIGRATIONS) + 1):
            self._con.execute("BEGIN TRANSACTION")
            try:
                self._con.execute(MIGRATIONS[version - 1])
                self._con.execute(
                    "INSERT INTO schema_migrations VALUES (?, ?)", [version, datetime.now(UTC)]
                )
                self._con.execute("COMMIT")
            except BaseException:
                self._con.execute("ROLLBACK")
                raise

    def schema_version(self) -> int:
        exists = self._con.execute(
            "SELECT count(*) FROM information_schema.tables "
            "WHERE table_catalog = ? AND table_name = 'schema_migrations'",
            [_ALIAS],
        ).fetchone()
        if not exists or not exists[0]:
            return 0
        row = self._con.execute(
            "SELECT coalesce(max(version), 0) FROM schema_migrations"
        ).fetchone()
        return int(row[0]) if row else 0

    def _stored(self, ids: list[str]) -> dict[str, Record]:
        return {
            row[0]: Record.model_validate_json(row[1])
            for row in self._con.execute(
                "SELECT id, data FROM records WHERE list_contains(?, id)", [ids]
            ).fetchall()
        }

    def changed(self, records: Iterable[Record]) -> list[Record]:
        """New records, or records whose content differs from the stored copy."""
        batch: dict[str, Record] = {r.id: r for r in records}
        stored = self._stored(list(batch))
        return [
            r for r in batch.values() if r.id not in stored or _content(stored[r.id]) != _content(r)
        ]

    def upsert(self, records: Iterable[Record]) -> UpsertResult:
        """Idempotent by id; a refetch that only changes ``fetched_at`` counts as unchanged."""
        batch: dict[str, Record] = {r.id: r for r in records}
        if not batch:
            return UpsertResult()
        existing = self._stored(list(batch))
        now = datetime.now(UTC)
        inserts: list[InsertRow] = []
        updates: list[UpdateRow] = []
        unchanged = 0
        for record in batch.values():
            previous = existing.get(record.id)
            if previous is None:
                inserts.append((*self._row(record), now, now))
            elif _comparable(previous) != _comparable(record):
                updates.append((*self._row(record)[1:], now, record.id))
            else:
                unchanged += 1
        self._con.execute("BEGIN TRANSACTION")
        try:
            if inserts:
                self._con.executemany(
                    "INSERT INTO records VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", inserts
                )
            if updates:
                self._con.executemany(
                    "UPDATE records SET source_type = ?, source_instance = ?, created_at = ?, "
                    "content_hash = ?, author_pseudonym = ?, purpose = ?, data = ?, "
                    "updated_at = ? WHERE id = ?",
                    updates,
                )
            self._con.execute("COMMIT")
        except BaseException:
            self._con.execute("ROLLBACK")
            raise
        return UpsertResult(inserted=len(inserts), updated=len(updates), unchanged=unchanged)

    @staticmethod
    def _row(record: Record) -> RecordRow:
        return (
            record.id,
            record.source.type,
            record.source.instance,
            record.created_at,
            record.content_hash,
            record.author.pseudonym if record.author else None,
            record.purpose,
            record.model_dump_json(),
        )

    def get(self, record_id: str) -> Record | None:
        row = self._con.execute("SELECT data FROM records WHERE id = ?", [record_id]).fetchone()
        return Record.model_validate_json(row[0]) if row else None

    def count(self, *, source_type: str | None = None) -> int:
        if source_type is None:
            row = self._con.execute("SELECT count(*) FROM records").fetchone()
        else:
            row = self._con.execute(
                "SELECT count(*) FROM records WHERE source_type = ?", [source_type]
            ).fetchone()
        return int(row[0]) if row else 0

    def iter_records(
        self,
        *,
        source_type: str | None = None,
        author_pseudonym: str | None = None,
        since: datetime | None = None,
        limit: int | None = None,
        batch_size: int = 500,
    ) -> Iterator[Record]:
        clauses, params = _filters(
            source_type=source_type, author_pseudonym=author_pseudonym, since=since
        )
        sql = "SELECT data FROM records"
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += " ORDER BY created_at, id"
        if limit is not None:
            sql += " LIMIT ?"
            params.append(limit)
        result = self._con.execute(sql, params)
        while rows := result.fetchmany(batch_size):
            for (data,) in rows:
                yield Record.model_validate_json(data)

    def delete(
        self,
        *,
        source_type: str | None = None,
        source_instance: str | None = None,
        author_pseudonym: str | None = None,
        before: datetime | None = None,
    ) -> int:
        """Delete matching records; at least one filter is required. Returns the count."""
        clauses, params = _filters(
            source_type=source_type,
            source_instance=source_instance,
            author_pseudonym=author_pseudonym,
            before=before,
        )
        if not clauses:
            raise StoreError("delete needs at least one filter")
        ids = [
            str(r[0])
            for r in self._con.execute(
                "DELETE FROM records WHERE " + " AND ".join(clauses) + " RETURNING id",  # noqa: S608
                params,
            ).fetchall()
        ]
        self._forget_derived(ids)
        return len(ids)

    def _forget_derived(self, ids: list[str]) -> None:
        """Erasure reaches derived data: theme membership, theme centroids and embeddings."""
        if ids:
            self._unassign(ids)
            self._con.execute("DELETE FROM embeddings WHERE list_contains(?, record_id)", [ids])
            self._con.execute(
                "DELETE FROM enrichment_retries WHERE list_contains(?, record_id)", [ids]
            )

    def retry_records(self, pipeline: str, source: str, limit: int) -> list[Record]:
        """Stored records of ``pipeline``/``source`` whose enrichment failed, oldest first."""
        rows = self._con.execute(
            "SELECT r.data FROM enrichment_retries q JOIN records r ON r.id = q.record_id "
            "WHERE q.pipeline = ? AND q.source = ? ORDER BY r.created_at, r.id LIMIT ?",
            [pipeline, source, limit],
        ).fetchall()
        return [Record.model_validate_json(data) for (data,) in rows]

    def track_retries(
        self, pipeline: str, source: str, *, done: Iterable[str], failed: Iterable[str]
    ) -> None:
        """Forget ``done`` records and queue ``failed`` ones for the next run."""
        cleared = list(done)
        if cleared:
            self._con.execute(
                "DELETE FROM enrichment_retries WHERE pipeline = ? AND source = ? "
                "AND list_contains(?, record_id)",
                [pipeline, source, cleared],
            )
        queued = list(failed)
        if queued:
            self._con.executemany(
                "INSERT INTO enrichment_retries VALUES (?, ?, ?) ON CONFLICT DO NOTHING",
                [(pipeline, source, rid) for rid in queued],
            )

    def get_cursor(self, pipeline: str, source: str) -> Cursor | None:
        row = self._con.execute(
            "SELECT cursor FROM cursors WHERE pipeline = ? AND source = ?", [pipeline, source]
        ).fetchone()
        if not row:
            return None
        value: Cursor = json.loads(row[0])
        return value

    def set_cursor(self, pipeline: str, source: str, cursor: Cursor) -> None:
        self._con.execute(
            "INSERT INTO cursors VALUES (?, ?, ?, ?) ON CONFLICT (pipeline, source) "
            "DO UPDATE SET cursor = excluded.cursor, updated_at = excluded.updated_at",
            [pipeline, source, json.dumps(cursor), datetime.now(UTC)],
        )

    def search(self, query: Query, *, limit: int = 20, newest_first: bool = True) -> list[Record]:
        where, params = query.where()
        order = "DESC" if newest_first else "ASC"
        rows = self._con.execute(
            f"SELECT data FROM records{where} ORDER BY created_at {order}, id LIMIT ?",  # noqa: S608
            [*params, limit],
        ).fetchall()
        return [Record.model_validate_json(data) for (data,) in rows]

    def stats(self, query: Query, group_by: GroupBy, *, limit: int = 50) -> list[StatRow]:
        where, params = query.where()
        key = _GROUPS[group_by]
        ordering = "key" if group_by in ("day", "week", "month", "rating") else "n DESC, key"
        rows = self._con.execute(
            f"SELECT CAST({key} AS VARCHAR) AS key, count(*) AS n, "  # noqa: S608 whitelisted
            f"avg(CAST(json_extract_string(data, '$.rating') AS DOUBLE)) FROM records{where} "
            f"GROUP BY key ORDER BY {ordering} LIMIT ?",
            [*params, limit],
        ).fetchall()
        return [StatRow(key=r[0], count=int(r[1]), avg_rating=r[2]) for r in rows]

    def audit(self, action: str, detail: dict[str, str | int | None]) -> None:
        """Append to the accountability log. Never pass raw personal data in ``detail``."""
        self._con.execute(
            "INSERT INTO audit_log VALUES (?, ?, ?)",
            [datetime.now(UTC), action, json.dumps(detail, sort_keys=True)],
        )

    def audit_log(self, *, limit: int = 100) -> list[tuple[datetime, str, str]]:
        rows = self._con.execute(
            "SELECT epoch_us(logged_at), action, detail FROM audit_log "
            "ORDER BY logged_at DESC LIMIT ?",
            [limit],
        ).fetchall()
        return [(datetime.fromtimestamp(r[0] / 1e6, UTC), str(r[1]), str(r[2])) for r in rows]
