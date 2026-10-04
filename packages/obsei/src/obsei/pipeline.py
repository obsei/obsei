"""Ingest engine: fetch, redact, enrich, deliver, store, then advance the cursor.

A batch is stored and its cursor advanced only after every sink accepted it, so a failed
run is retried from the same position (at-least-once; sinks are idempotent by record id).
Only new or changed records are enriched and delivered. Records an enricher could not label
are stored, reported and enriched again on the next run. Records a filtering enricher drops are
counted and neither delivered nor stored. With routes, each record is given a ``route``
enrichment before delivery and is stored with it.

Store calls run under the optional ``lock``; fetching, enrichers and sinks run outside it, so a
slow source or model does not block other users of a shared store.
"""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from contextlib import AbstractContextManager, nullcontext
from dataclasses import dataclass, field
from datetime import UTC, datetime
from itertools import islice
from typing import Protocol, TypeAlias, runtime_checkable

from obsei.core.protocols import Cursor, Drops, Enricher, ReportsErrors, Sink, Source
from obsei.core.record import Record
from obsei.routing import Router, routed_to
from obsei.store import Store

RETRY_LIMIT = 500
Lock: TypeAlias = AbstractContextManager[object]


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
    """Without ``redactor`` you must pass ``allow_unredacted=True``. ``sink_keys`` name the sinks
    (default: each sink's name); with a ``router``, sinks it names receive only the records routed
    to them and the others receive every record."""

    name: str
    sources: Sequence[SourceSpec]
    enrichers: Sequence[Enricher] = ()
    sinks: Sequence[Sink] = ()
    redactor: Redactor | None = None
    allow_unredacted: bool = False
    batch_size: int = 100
    sink_keys: Sequence[str] = ()
    router: Router | None = None

    def __post_init__(self) -> None:
        if self.redactor is None and not self.allow_unredacted:
            raise PipelineError(f"pipeline {self.name!r} needs a redactor or allow_unredacted=True")
        if self.batch_size < 1:
            raise PipelineError("batch_size must be at least 1")
        keys = [spec.key for spec in self.sources]
        if len(keys) != len(set(keys)):
            raise PipelineError("source keys must be unique within a pipeline")
        if self.sink_keys and len(self.sink_keys) != len(self.sinks):
            raise PipelineError("sink_keys must name every sink")
        if self.router is not None:
            names = self.keys
            if len(names) != len(set(names)):
                raise PipelineError("sink keys must be unique within a routed pipeline")
            unknown = self.router.targets - set(names)
            if unknown:
                raise PipelineError(f"routes name unknown sinks: {sorted(unknown)}")

    @property
    def keys(self) -> list[str]:
        return list(self.sink_keys) if self.sink_keys else [s.name for s in self.sinks]


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
    failed: dict[str, int] = field(default_factory=dict)
    dropped: dict[str, int] = field(default_factory=dict)
    errors: dict[str, str] = field(default_factory=dict)

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
) -> tuple[list[Record], list[str]]:
    """The enriched records still kept, and the ids of dropped ones."""
    dropped: list[str] = []
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
        missing = sum(e is None for e in results)
        if missing:
            report.failed[enricher.name] = report.failed.get(enricher.name, 0) + missing
            if isinstance(enricher, ReportsErrors) and enricher.last_error:
                report.errors[enricher.name] = enricher.last_error
        if isinstance(enricher, Drops):
            kept = [r for r in records if enricher.keep(r)]
            if len(kept) < len(records):
                ids = {r.id for r in kept}
                dropped.extend(r.id for r in records if r.id not in ids)
                report.dropped[enricher.name] = (
                    report.dropped.get(enricher.name, 0) + len(records) - len(kept)
                )
            records = kept
    return records, dropped


def _deliver(pipeline: Pipeline, records: list[Record], report: RunReport) -> None:
    targets = pipeline.router.targets if pipeline.router else frozenset()
    for key, sink in zip(pipeline.keys, pipeline.sinks, strict=True):
        batch = [r for r in records if key in routed_to(r)] if key in targets else records
        result = sink.send(batch)
        if result.errors:
            raise PipelineError(f"sink {key!r} failed: {'; '.join(result.errors)}")
        report.sent[key] = report.sent.get(key, 0) + result.sent


def _process(
    pipeline: Pipeline,
    key: str,
    records: list[Record],
    store: Store,
    *,
    guard: Lock,
    report: RunReport,
    cursor: Cursor | None = None,
) -> int:
    records, dropped = _enrich(pipeline.enrichers, records, report)
    if pipeline.router is not None:
        records = [pipeline.router.apply(r) for r in records]
    _deliver(pipeline, records, report)
    names = [e.name for e in pipeline.enrichers]
    failed = {r.id for r in records if any(n not in r.enrichments for n in names)}
    with guard:
        result = store.upsert(records)
        store.track_retries(
            pipeline.name,
            key,
            done=[*dropped, *(r.id for r in records if r.id not in failed)],
            failed=sorted(failed),
        )
        if cursor is not None:
            store.set_cursor(pipeline.name, key, cursor)
    return result.inserted + result.updated


def run(pipeline: Pipeline, store: Store, *, lock: Lock | None = None) -> RunReport:
    guard: Lock = lock or nullcontext()
    report = RunReport(pipeline=pipeline.name, started_at=datetime.now(UTC))
    for spec in pipeline.sources:
        source_report = report.sources.setdefault(spec.key, SourceReport())
        with guard:
            cursor = store.get_cursor(pipeline.name, spec.key)
            retry = (
                store.retry_records(pipeline.name, spec.key, RETRY_LIMIT)
                if pipeline.enrichers
                else []
            )
        for start in range(0, len(retry), pipeline.batch_size):
            batch_records = retry[start : start + pipeline.batch_size]
            source_report.stored += _process(
                pipeline, spec.key, batch_records, store, guard=guard, report=report
            )
        for batch in _batches(spec.source.fetch(cursor), pipeline.batch_size):
            records = [record for record, _ in batch]
            source_report.fetched += len(records)
            if pipeline.redactor is not None:
                records = list(pipeline.redactor.redact(records))
            with guard:
                changed = store.changed(records)
            source_report.changed += len(changed)
            if changed:
                source_report.stored += _process(
                    pipeline,
                    spec.key,
                    changed,
                    store,
                    guard=guard,
                    report=report,
                    cursor=batch[-1][1],
                )
            else:
                with guard:
                    store.set_cursor(pipeline.name, spec.key, batch[-1][1])
    report.finished_at = datetime.now(UTC)
    return report
