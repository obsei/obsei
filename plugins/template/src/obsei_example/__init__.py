from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from typing import ClassVar

from pydantic import BaseModel, ConfigDict

from obsei.core.context import Context
from obsei.core.plugin import factory
from obsei.core.protocols import Cursor
from obsei.core.record import Record, SourceRef
from obsei.core.registry import Registry


class ExampleConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    greeting: str = "hello"


class ExampleSource:
    name: ClassVar[str] = "example"

    def __init__(self, config: ExampleConfig, ctx: Context) -> None:
        self.config = config
        self.ctx = ctx

    def fetch(self, cursor: Cursor | None) -> Iterator[tuple[Record, Cursor]]:
        record = Record(
            source=SourceRef(type=self.name, native_id="1"),
            text=self.config.greeting,
            created_at=datetime.now(UTC),
        )
        yield record, {"done": True}


def register(registry: Registry) -> None:
    registry.add_source("example", factory(ExampleConfig, ExampleSource))
