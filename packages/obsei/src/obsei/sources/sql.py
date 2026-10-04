"""Any SQL database SQLAlchemy supports (Postgres, MySQL, SQL Server, Oracle, Snowflake, BigQuery,
SQLite, ...). Needs ``pip install 'obsei[sql]'`` plus the database driver.

The query receives ``:since`` (the newest ``cursor_column`` value seen, or ``initial_since``) and
must return rows ordered by that column.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from datetime import UTC, datetime
from typing import ClassVar

from pydantic import BaseModel, ConfigDict, Field, JsonValue

from obsei.core.context import Context
from obsei.core.protocols import Cursor
from obsei.core.record import Record
from obsei.sources._common import FieldMap, as_text, map_item


class SqlConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    url_env: str = Field(description="Environment variable holding the SQLAlchemy URL.")
    query: str = Field(description="SELECT ... WHERE updated_at > :since ORDER BY updated_at")
    cursor_column: str = "updated_at"
    initial_since: str = "1970-01-01T00:00:00+00:00"
    instance: str = "default"
    fields: FieldMap = Field(default_factory=FieldMap)
    fetch_size: int = Field(default=1000, ge=1)


class SqlError(RuntimeError):
    pass


def _json(value: object) -> JsonValue:
    if value is None or isinstance(value, str | int | float | bool):
        return value
    if isinstance(value, datetime):
        return (value if value.tzinfo else value.replace(tzinfo=UTC)).isoformat()
    return str(value)


class SqlSource:
    name: ClassVar[str] = "sql"

    def __init__(self, config: SqlConfig, ctx: Context) -> None:
        try:
            import sqlalchemy  # noqa: PLC0415
        except ImportError:
            raise SqlError("the sql source needs: pip install 'obsei[sql]'") from None
        url = os.environ.get(config.url_env)
        if not url:
            raise SqlError(f"{config.url_env} is not set")
        if not config.query.lstrip().lower().startswith(("select", "with")):
            raise SqlError("query must be a SELECT")
        self.config = config
        self.ctx = ctx
        self.engine = sqlalchemy.create_engine(url)
        self.statement = sqlalchemy.text(config.query)

    def fetch(self, cursor: Cursor | None) -> Iterator[tuple[Record, Cursor]]:
        since = cursor.get("since") if cursor else None
        position = since if isinstance(since, str) else self.config.initial_since
        now = datetime.now(UTC)
        with self.engine.connect() as raw:
            connection = raw.execution_options(
                stream_results=True, yield_per=self.config.fetch_size
            )
            for row in connection.execute(self.statement, {"since": position}).mappings():
                item: JsonValue = {str(k): _json(v) for k, v in row.items()}
                record = map_item(
                    item,
                    self.config.fields,
                    source_type=self.name,
                    instance=self.config.instance,
                    ctx=self.ctx,
                    default_time=now,
                )
                position = as_text(_json(row.get(self.config.cursor_column))) or position
                if record is not None:
                    yield record, {"since": position}
