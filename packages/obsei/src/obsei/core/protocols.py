"""Plugin protocols. Sources fetch, enrichers annotate, sinks deliver.

The API is deliberately synchronous: the engine handles batching and concurrency,
so plugin authors only write plain functions over records.
"""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from typing import ClassVar, Protocol, runtime_checkable

from pydantic import BaseModel, Field

from obsei.core.record import Enrichment, Record

#: Opaque, JSON-serialisable position in a source (e.g. a timestamp or page token).
Cursor = dict[str, str | int | float | None]


class SinkResult(BaseModel):
    """What a sink did with a batch."""

    sent: int = 0
    skipped: int = 0
    errors: list[str] = Field(default_factory=list)


@runtime_checkable
class Source(Protocol):
    """Pulls items from one system and yields records with an updated cursor."""

    name: ClassVar[str]

    def fetch(self, cursor: Cursor | None) -> Iterator[tuple[Record, Cursor]]: ...


@runtime_checkable
class Enricher(Protocol):
    """Adds one kind of annotation. Returns one result (or None) per input record."""

    name: ClassVar[str]
    version: ClassVar[str]

    def enrich(self, batch: Sequence[Record]) -> Sequence[Enrichment | None]: ...


@runtime_checkable
class Sink(Protocol):
    """Delivers records somewhere. Must be idempotent by ``Record.id``."""

    name: ClassVar[str]

    def send(self, batch: Sequence[Record]) -> SinkResult: ...
