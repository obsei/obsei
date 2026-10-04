"""Ingest engine: fetch, redact, enrich, deliver, store, then advance the cursor.

A batch is stored and its cursor advanced only after every sink accepted it, so a failed
run is retried from the same position (at-least-once; sinks are idempotent by record id).
Only new or changed records are enriched and delivered.
"""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from itertools import islice
from typing import Protocol, runtime_checkable

from obsei.core.protocols import Cursor, Enricher, Sink, Source
from obsei.core.record import Record
from obsei.store import Store


@runtime_checkable
class Redactor(Protocol):
    def redact(self, batch: Sequence[Record]) -> Sequence[Record]: ...


class PipelineError(Exception):
    pass


@dataclass(frozen=True)
class SourceSpec:
    key: str
    source: Source


@dataclass(frozen=True)
class Pipeline:
    """Without ``redactor`` you must pass ``allow_unredacted=True``."""

    name: str
    sources: Sequence[SourceSpec]
    enrichers: Sequence[Enricher] = ()
    sinks: Sequence[Sink] = ()
    redactor: Redactor | None = None
    allow_unredacted: bool = False
    batch_size: int = 100

    def __post_init__(self) -> None:
        if self.redactor is None and not self.allow_unredacted:
            raise PipelineError(f"pipeline {self.name!r} needs a redactor or allow_unredacted=True")
        if self.batch_size < 1:
            raise PipelineError("batch_size must be at least 1")
        keys = [spec.key for spec in self.sources]
        if len(keys) != len(set(keys)):
            raise PipelineError("source keys must be unique within a pipeline")


@dataclass
class SourceReport:
    fetched: int = 0
    changed: int = 0
    stored: int = 0


@dataclass
class RunReport:
    pipeline: str
    started_at: datetime
    finished_at: datetime | None = None
    sources: dict[str, SourceReport] = field(default_factory=dict)
    enriched: dict[str, int] = field(default_factory=dict)
    sent: dict[str, int] = field(default_factory=dict)

    @property
    def fetched(self) -> int:
        return sum(r.fetched for r in self.sources.values())

    @property
    def stored(self) -> int:
        return sum(r.stored for r in self.sources.values())


def _batches(
    items: Iterator[tuple[Record, Cursor]], size: int
) -> Iterator[list[tuple[Record, Cursor]]]:
    while batch := list(islice(items, size)):
        yield batch


def _enrich(
    enrichers: Sequence[Enricher], records: list[Record], report: RunReport
) -> list[Record]:
    for enricher in enrichers:
        results = enricher.enrich(records)
        if len(results) != len(records):
            raise PipelineError(
                f"enricher {enricher.name!r} returned {len(results)} results "
                f"for {len(records)} records"
            )
        records = [
            r if e is None else r.with_enrichment(enricher.name, e)
            for r, e in zip(records, results, strict=True)
        ]
        report.enriched[enricher.name] = report.enriched.get(enricher.name, 0) + sum(
            e is not None for e in results
        )
    return records


def _deliver(sinks: Sequence[Sink], records: list[Record], report: RunReport) -> None:
    for sink in sinks:
        result = sink.send(records)
        if result.errors:
            raise PipelineError(f"sink {sink.name!r} failed: {'; '.join(result.errors)}")
        report.sent[sink.name] = report.sent.get(sink.name, 0) + result.sent


def run(pipeline: Pipeline, store: Store) -> RunReport:
    report = RunReport(pipeline=pipeline.name, started_at=datetime.now(UTC))
    for spec in pipeline.sources:
        source_report = report.sources.setdefault(spec.key, SourceReport())
        cursor = store.get_cursor(pipeline.name, spec.key)
        for batch in _batches(spec.source.fetch(cursor), pipeline.batch_size):
            records = [record for record, _ in batch]
            source_report.fetched += len(records)
            if pipeline.redactor is not None:
                records = list(pipeline.redactor.redact(records))
            changed = store.changed(records)
            source_report.changed += len(changed)
            if changed:
                changed = _enrich(pipeline.enrichers, changed, report)
                _deliver(pipeline.sinks, changed, report)
                result = store.upsert(changed)
                source_report.stored += result.inserted + result.updated
            store.set_cursor(pipeline.name, spec.key, batch[-1][1])
    report.finished_at = datetime.now(UTC)
    return report
