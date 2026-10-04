"""Write batches as Parquet files for warehouses, notebooks and BI tools."""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from pathlib import Path
from typing import ClassVar

import duckdb
from pydantic import BaseModel, ConfigDict

from obsei.core.context import Context
from obsei.core.protocols import SinkResult
from obsei.core.record import Record

COLUMNS = """
    id VARCHAR, source_type VARCHAR, source_instance VARCHAR, native_id VARCHAR, url VARCHAR,
    text VARCHAR, created_at TIMESTAMPTZ, rating DOUBLE, lang VARCHAR, author_pseudonym VARCHAR,
    context JSON, enrichments JSON
"""

INSERT = "INSERT INTO batch VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"


class ParquetConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    directory: Path
    include_authors: bool = False


class ParquetSink:
    """File names are derived from the batch's ids and hashes, so a retried batch overwrites."""

    name: ClassVar[str] = "parquet"

    def __init__(self, config: ParquetConfig, ctx: Context) -> None:
        self.config = config
        config.directory.mkdir(parents=True, exist_ok=True)

    def send(self, batch: Sequence[Record]) -> SinkResult:
        if not batch:
            return SinkResult()
        key = hashlib.sha256(
            "".join(f"{r.id}{r.content_hash}" for r in batch).encode()
        ).hexdigest()[:24]
        target = self.config.directory / f"part-{key}.parquet"
        rows = [
            (
                r.id,
                r.source.type,
                r.source.instance,
                r.source.native_id,
                r.source.url,
                r.text,
                r.created_at,
                r.rating,
                r.lang,
                r.author.pseudonym if r.author and self.config.include_authors else None,
                r.model_dump_json(include={"context"}),
                r.model_dump_json(include={"enrichments"}),
            )
            for r in batch
        ]
        with duckdb.connect() as con:
            con.execute(f"CREATE TABLE batch ({COLUMNS})")
            con.executemany(INSERT, rows)
            con.table("batch").write_parquet(str(target))
        return SinkResult(sent=len(batch))
