from __future__ import annotations

from collections.abc import Iterator, Sequence
from typing import ClassVar, Protocol, TypeAlias, runtime_checkable

from pydantic import BaseModel, Field

from obsei.core.record import Enrichment, Record

CursorValue: TypeAlias = str | int | float | bool | None
Cursor: TypeAlias = dict[str, CursorValue]


class SinkResult(BaseModel):
    sent: int = 0
    skipped: int = 0
    errors: list[str] = Field(default_factory=list)


@runtime_checkable
class Source(Protocol):
    name: ClassVar[str]

    def fetch(self, cursor: Cursor | None) -> Iterator[tuple[Record, Cursor]]: ...


@runtime_checkable
class Enricher(Protocol):
    name: ClassVar[str]
    version: ClassVar[str]

    def enrich(self, batch: Sequence[Record]) -> Sequence[Enrichment | None]: ...


@runtime_checkable
class Sink(Protocol):
    """Must be idempotent by ``Record.id``."""

    name: ClassVar[str]

    def send(self, batch: Sequence[Record]) -> SinkResult: ...
