"""CSV and JSON Lines files. Rows are re-read each run; unchanged rows are skipped downstream."""

from __future__ import annotations

import csv
import json
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import ClassVar

from pydantic import BaseModel, ConfigDict, Field, JsonValue

from obsei.core.context import Context
from obsei.core.protocols import Cursor
from obsei.core.record import Record
from obsei.sources._common import FieldMap, map_item


class FileConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: Path
    instance: str = "default"
    fields: FieldMap = Field(default_factory=FieldMap)
    encoding: str = "utf-8-sig"


class CsvConfig(FileConfig):
    delimiter: str = Field(default=",", min_length=1, max_length=1)


class _FileSource:
    name: ClassVar[str]

    def __init__(self, config: FileConfig, ctx: Context) -> None:
        self.config = config
        self.ctx = ctx

    def _rows(self) -> Iterator[JsonValue]:
        raise NotImplementedError

    def fetch(self, cursor: Cursor | None) -> Iterator[tuple[Record, Cursor]]:
        mtime = datetime.fromtimestamp(self.config.path.stat().st_mtime, UTC)
        for line, row in enumerate(self._rows(), start=1):
            record = map_item(
                row,
                self.config.fields,
                source_type=self.name,
                instance=self.config.instance,
                ctx=self.ctx,
                default_time=mtime,
            )
            if record is not None:
                yield record, {"line": line}


class CsvSource(_FileSource):
    name: ClassVar[str] = "csv"

    def __init__(self, config: CsvConfig, ctx: Context) -> None:
        super().__init__(config, ctx)
        self.delimiter = config.delimiter

    def _rows(self) -> Iterator[JsonValue]:
        with self.config.path.open(encoding=self.config.encoding, newline="") as handle:
            for row in csv.DictReader(handle, delimiter=self.delimiter):
                yield {key: value for key, value in row.items() if key is not None}


class JsonlSource(_FileSource):
    name: ClassVar[str] = "jsonl"

    def _rows(self) -> Iterator[JsonValue]:
        with self.config.path.open(encoding=self.config.encoding) as handle:
            for number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                try:
                    row: JsonValue = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise ValueError(f"{self.config.path}:{number}: invalid JSON: {exc}") from None
                yield row
