"""DuckDB-backed feedback store: one file per deployment, encrypted at rest by default.

Records are kept as their full JSON plus a few extracted columns for filtering, so the
stored form always round-trips to the ``Record`` model. Re-ingesting an item is
idempotent: ``upsert`` inserts new records, updates changed ones and skips the rest.

DuckDB allows a single writer process. Run ingestion from one process (``obsei serve``
or a single ``obsei run``) and open the store read-only everywhere else.
"""

from __future__ import annotations

import json
import os
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from types import TracebackType
from typing import Any, Self

import duckdb

from obsei.core.protocols import Cursor
from obsei.core.record import Record

DB_KEY_ENV_VAR = "OBSEI_DB_KEY"
MIN_KEY_LENGTH = 16
_ALIAS = "obsei"

#: Ordered schema migrations. Never edit a released entry; append a new one instead.
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
)


class StoreError(Exception):
    """The store could not be opened or used."""


class EncryptionUnavailableError(StoreError):
    """DuckDB cannot write encrypted files because its OpenSSL-backed extension is missing."""


@dataclass(frozen=True)
class UpsertResult:
    inserted: int = 0
    updated: int = 0
    unchanged: int = 0


def load_db_key(env_var: str = DB_KEY_ENV_VAR) -> str | None:
    """Read the database encryption key from the environment, if set."""
    key = os.environ.get(env_var) or None
    if key is not None and len(key) < MIN_KEY_LENGTH:
        raise StoreError(f"{env_var} must be at least {MIN_KEY_LENGTH} characters")
    return key


def _sql_literal(value: str) -> str:
    if "\x00" in value:
        raise StoreError("value must not contain NUL characters")
    return "'" + value.replace("'", "''") + "'"


def _comparable(record: Record) -> dict[str, Any]:
    # fetched_at changes on every fetch, so it doesn't count as a content change.
    return record.model_dump(mode="json", exclude={"fetched_at"})


class Store:
    """A feedback store backed by a single DuckDB file (or memory for tests).

    Pass ``encryption_key`` to encrypt at rest. Without a key you must set
    ``allow_unencrypted=True``, e.g. when the disk itself is encrypted.
    """

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

    # -- lifecycle -----------------------------------------------------------------

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

    # -- records -------------------------------------------------------------------

    def upsert(self, records: Iterable[Record]) -> UpsertResult:
        """Insert new records, update changed ones, skip identical ones. Idempotent by id."""
        batch: dict[str, Record] = {r.id: r for r in records}
        if not batch:
            return UpsertResult()
        existing = {
            row[0]: Record.model_validate_json(row[1])
            for row in self._con.execute(
                "SELECT id, data FROM records WHERE list_contains(?, id)", [list(batch)]
            ).fetchall()
        }
        now = datetime.now(UTC)
        inserts: list[list[Any]] = []
        updates: list[list[Any]] = []
        unchanged = 0
        for record in batch.values():
            previous = existing.get(record.id)
            if previous is None:
                inserts.append([*self._row(record), now, now])
            elif _comparable(previous) != _comparable(record):
                updates.append([*self._row(record)[1:], now, record.id])
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
    def _row(record: Record) -> list[Any]:
        return [
            record.id,
            record.source.type,
            record.source.instance,
            record.created_at,
            record.content_hash,
            record.author.pseudonym if record.author else None,
            record.purpose,
            record.model_dump_json(),
        ]

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
        since: datetime | None = None,
        limit: int | None = None,
        batch_size: int = 500,
    ) -> Iterator[Record]:
        """Yield records ordered by creation time, optionally filtered."""
        clauses: list[str] = []
        params: list[Any] = []
        if source_type is not None:
            clauses.append("source_type = ?")
            params.append(source_type)
        if since is not None:
            if since.tzinfo is None:
                raise ValueError("since must be timezone-aware")
            clauses.append("created_at >= ?")
            params.append(since)
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

    # -- cursors -------------------------------------------------------------------

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
