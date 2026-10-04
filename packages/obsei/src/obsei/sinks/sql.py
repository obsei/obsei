"""Upsert records into a warehouse or database table (Postgres, Snowflake, BigQuery, SQL Server,
MySQL, ...) through SQLAlchemy. Needs ``pip install 'obsei[sql]'`` plus the driver."""

from __future__ import annotations

import os
from collections.abc import Sequence
from typing import ClassVar

from pydantic import BaseModel, ConfigDict, Field

from obsei.core.context import Context
from obsei.core.protocols import SinkResult
from obsei.core.record import Record


class SqlSinkConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    url_env: str
    table: str = Field(default="obsei_feedback", pattern=r"^[A-Za-z_][A-Za-z0-9_]{0,62}$")
    schema_name: str | None = Field(default=None, pattern=r"^[A-Za-z_][A-Za-z0-9_]{0,62}$")
    include_authors: bool = False


class SqlSinkError(RuntimeError):
    pass


class SqlSink:
    name: ClassVar[str] = "sql"

    def __init__(self, config: SqlSinkConfig, ctx: Context) -> None:
        try:
            import sqlalchemy as sa  # noqa: PLC0415
        except ImportError:
            raise SqlSinkError("the sql sink needs: pip install 'obsei[sql]'") from None
        url = os.environ.get(config.url_env)
        if not url:
            raise SqlSinkError(f"{config.url_env} is not set")
        self.config = config
        self.engine = sa.create_engine(url)
        self.table = sa.Table(
            config.table,
            sa.MetaData(schema=config.schema_name),
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("source_type", sa.String(64), nullable=False),
            sa.Column("source_instance", sa.String(255), nullable=False),
            sa.Column("native_id", sa.String(512), nullable=False),
            sa.Column("url", sa.Text),
            sa.Column("text", sa.Text, nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("rating", sa.Float),
            sa.Column("lang", sa.String(16)),
            sa.Column("author_pseudonym", sa.String(64)),
            sa.Column("context", sa.JSON),
            sa.Column("enrichments", sa.JSON),
            sa.Column("content_hash", sa.String(64), nullable=False),
        )
        self.table.metadata.create_all(self.engine)

    def send(self, batch: Sequence[Record]) -> SinkResult:
        if not batch:
            return SinkResult()
        rows = [
            {
                "id": r.id,
                "source_type": r.source.type,
                "source_instance": r.source.instance,
                "native_id": r.source.native_id,
                "url": r.source.url,
                "text": r.text,
                "created_at": r.created_at,
                "rating": r.rating,
                "lang": r.lang,
                "author_pseudonym": r.author.pseudonym
                if r.author and self.config.include_authors
                else None,
                "context": r.context,
                "enrichments": {k: v.model_dump(mode="json") for k, v in r.enrichments.items()},
                "content_hash": r.content_hash,
            }
            for r in batch
        ]
        with self.engine.begin() as connection:
            connection.execute(
                self.table.delete().where(self.table.c.id.in_([r.id for r in batch]))
            )
            connection.execute(self.table.insert(), rows)
        return SinkResult(sent=len(batch))
