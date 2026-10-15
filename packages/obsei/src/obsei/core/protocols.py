from __future__ import annotations

from collections.abc import Iterator, Sequence
from typing import ClassVar, Literal, Protocol, TypeAlias, runtime_checkable

from pydantic import BaseModel, Field

from obsei.core.record import Enrichment, Record

CursorValue: TypeAlias = str | int | float | bool | None
Cursor: TypeAlias = dict[str, CursorValue]
AlertKind: TypeAlias = Literal[
    "theme_spike", "new_theme", "digest", "review_queue", "pipeline_health"
]


class EventDelivery(BaseModel):
    """The final outcome of one event a sink posted; the pipeline keeps it in the store."""

    event_id: str
    event_type: str
    host: str
    attempts: int
    status: int | None = None
    error: str | None = None


class SinkResult(BaseModel):
    sent: int = 0
    skipped: int = 0
    errors: list[str] = Field(default_factory=list)
    deliveries: list[EventDelivery] = Field(default_factory=list)


class Alert(BaseModel):
    """One aggregate alert: counts and redacted quotes from a k-anonymous theme, never authors."""

    alert: str
    kind: AlertKind
    key: str
    title: str
    lines: list[str] = Field(default_factory=list)
    count: int | None = None
    baseline: float | None = None
    theme: str | None = None
    quotes: list[str] = Field(default_factory=list)
    owner: str | None = None


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
class ReportsErrors(Protocol):
    """Optional for enrichers: why the most recent ``None`` result was returned."""

    @property
    def last_error(self) -> str | None: ...


@runtime_checkable
class Drops(Protocol):
    """Optional for enrichers: records ``keep`` rejects once enriched are dropped: not passed to
    later enrichers, delivered or stored."""

    def keep(self, record: Record) -> bool: ...


@runtime_checkable
class Binds(Protocol):
    """Optional for sinks: told the pipeline and sink key they deliver for."""

    def bind(self, pipeline: str, key: str) -> None: ...


@runtime_checkable
class Sink(Protocol):
    """Must be idempotent by ``Record.id``."""

    name: ClassVar[str]

    def send(self, batch: Sequence[Record]) -> SinkResult: ...


@runtime_checkable
class Alerts(Protocol):
    """Optional for sinks: deliver one aggregate alert as a single message or event."""

    def alert(self, alert: Alert) -> SinkResult: ...
