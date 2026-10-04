"""A drop folder: each new or modified CSV, JSON Lines or JSON file is ingested once.

Point SFTP uploads, a mounted bucket or a scheduled export at the folder.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import ClassVar

from pydantic import BaseModel, ConfigDict, Field, JsonValue

from obsei.core.context import Context
from obsei.core.protocols import Cursor
from obsei.core.record import Record
from obsei.sources._common import FieldMap, lookup, map_item
from obsei.sources.files import CsvConfig, CsvSource, FileConfig, JsonlSource


class FileDropConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    directory: Path
    pattern: str = "*"
    instance: str = "default"
    items_path: str | None = Field(default=None, description="For .json files holding a list.")
    fields: FieldMap = Field(default_factory=FieldMap)


class FileDropSource:
    name: ClassVar[str] = "filedrop"

    def __init__(self, config: FileDropConfig, ctx: Context) -> None:
        self.config = config
        self.ctx = ctx

    def _records(self, path: Path) -> Iterator[Record]:
        c = self.config
        suffix = path.suffix.lower()
        if suffix in (".csv", ".jsonl", ".ndjson"):
            if suffix == ".csv":
                reader: CsvSource | JsonlSource = CsvSource(
                    CsvConfig(path=path, instance=c.instance, fields=c.fields), self.ctx
                )
            else:
                reader = JsonlSource(
                    FileConfig(path=path, instance=c.instance, fields=c.fields), self.ctx
                )
            for record, _ in reader.fetch(None):
                source = record.source.model_copy(update={"type": self.name})
                yield record.model_copy(update={"source": source, "id": Record.make_id(source)})
        elif suffix == ".json":
            payload: JsonValue = json.loads(path.read_text(encoding="utf-8"))
            items = lookup(payload, c.items_path) if c.items_path else payload
            mtime = datetime.fromtimestamp(path.stat().st_mtime, UTC)
            for item in items if isinstance(items, list) else [items]:
                mapped = map_item(
                    item,
                    c.fields,
                    source_type=self.name,
                    instance=c.instance,
                    ctx=self.ctx,
                    default_time=mtime,
                )
                if mapped is not None:
                    yield mapped

    def fetch(self, cursor: Cursor | None) -> Iterator[tuple[Record, Cursor]]:
        state: Cursor = dict(cursor or {})
        files = sorted(p for p in self.config.directory.glob(self.config.pattern) if p.is_file())
        for path in files:
            stamp = datetime.fromtimestamp(path.stat().st_mtime, UTC).isoformat()
            if state.get(path.name) == stamp:
                continue
            records = list(self._records(path))
            for record in records[:-1]:
                yield record, dict(state)
            state[path.name] = stamp
            if records:
                yield records[-1], dict(state)
