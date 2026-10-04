import re
import threading
from collections.abc import Iterator, Sequence
from datetime import UTC, datetime
from typing import ClassVar

import pytest

from obsei import Enrichment, Record, SourceRef
from obsei.core.protocols import Cursor, Enricher, SinkResult
from obsei.pipeline import Pipeline, PipelineError, SourceSpec, run
from obsei.store import Store

T0 = datetime(2026, 9, 1, tzinfo=UTC)


class ListSource:
    name: ClassVar[str] = "list"

    def __init__(self, texts: list[str], *, honour_cursor: bool = True) -> None:
        self.texts = texts
        self.honour_cursor = honour_cursor

    def fetch(self, cursor: Cursor | None) -> Iterator[tuple[Record, Cursor]]:
        offset = cursor.get("offset") if cursor and self.honour_cursor else 0
        start = offset if isinstance(offset, int) else 0
        for i, text in enumerate(self.texts[start:], start=start):
            record = Record(
                source=SourceRef(type="list", native_id=str(i)), text=text, created_at=T0
            )
            yield record, {"offset": i + 1}


class LengthEnricher:
    name: ClassVar[str] = "length"
    version: ClassVar[str] = "1"

    def __init__(self) -> None:
        self.calls = 0

    def enrich(self, batch: Sequence[Record]) -> Sequence[Enrichment | None]:
        self.calls += len(batch)
        return [Enrichment(value=len(r.text), at=T0) for r in batch]


class BrokenEnricher:
    name: ClassVar[str] = "broken"
    version: ClassVar[str] = "1"

    def enrich(self, batch: Sequence[Record]) -> Sequence[Enrichment | None]:
        return []


class MemorySink:
    name: ClassVar[str] = "memory"

    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.received: list[Record] = []

    def send(self, batch: Sequence[Record]) -> SinkResult:
        if self.fail:
            return SinkResult(errors=["endpoint down"])
        self.received.extend(batch)
        return SinkResult(sent=len(batch))


class EmailRedactor:
    def redact(self, batch: Sequence[Record]) -> Sequence[Record]:
        return [r.model_copy(update={"text": re.sub(r"\S+@\S+", "<EMAIL>", r.text)}) for r in batch]


@pytest.fixture
def store() -> Store:
    return Store(allow_unencrypted=True)


def pipeline(
    source: ListSource,
    *,
    sinks: Sequence[MemorySink] = (),
    enrichers: Sequence[Enricher] = (),
    batch_size: int = 100,
) -> Pipeline:
    return Pipeline(
        name="daily",
        sources=[SourceSpec("reviews", source)],
        enrichers=enrichers,
        sinks=sinks,
        redactor=EmailRedactor(),
        batch_size=batch_size,
    )


def test_requires_redactor_or_explicit_opt_out() -> None:
    with pytest.raises(PipelineError, match="redactor"):
        Pipeline(name="p", sources=[SourceSpec("s", ListSource([]))])
    Pipeline(name="p", sources=[SourceSpec("s", ListSource([]))], allow_unredacted=True)


def test_duplicate_source_keys_rejected() -> None:
    with pytest.raises(PipelineError, match="unique"):
        Pipeline(
            name="p",
            sources=[SourceSpec("s", ListSource([])), SourceSpec("s", ListSource([]))],
            allow_unredacted=True,
        )


def test_first_run_redacts_enriches_delivers_and_stores(store: Store) -> None:
    sink, enricher = MemorySink(), LengthEnricher()
    report = run(
        pipeline(ListSource(["mail me at a@b.co", "slow app"]), sinks=[sink], enrichers=[enricher]),
        store,
    )
    assert report.fetched == 2
    assert report.stored == 2
    assert report.sent == {"memory": 2}
    assert report.enriched == {"length": 2}
    assert [r.text for r in sink.received] == ["mail me at <EMAIL>", "slow app"]
    assert all(r.enrichments["length"].value == len(r.text) for r in store.iter_records())
    assert store.get_cursor("daily", "reviews") == {"offset": 2}


def test_cursor_resumes_and_only_new_items_are_fetched(store: Store) -> None:
    source = ListSource(["a", "b"])
    run(pipeline(source), store)
    source.texts.append("c")
    report = run(pipeline(source), store)
    assert report.fetched == 1
    assert store.count() == 3


def test_unchanged_refetch_skips_enrichers_and_sinks(store: Store) -> None:
    source = ListSource(["a", "b"], honour_cursor=False)
    run(pipeline(source, sinks=[MemorySink()], enrichers=[LengthEnricher()]), store)
    sink, enricher = MemorySink(), LengthEnricher()
    report = run(pipeline(source, sinks=[sink], enrichers=[enricher]), store)
    assert report.fetched == 2
    assert report.sources["reviews"].changed == 0
    assert enricher.calls == 0
    assert sink.received == []


def test_edited_item_is_re_enriched_and_redelivered(store: Store) -> None:
    source = ListSource(["a", "b"], honour_cursor=False)
    run(pipeline(source, enrichers=[LengthEnricher()]), store)
    source.texts[1] = "b edited"
    sink = MemorySink()
    run(pipeline(source, sinks=[sink], enrichers=[LengthEnricher()]), store)
    assert [r.text for r in sink.received] == ["b edited"]
    stored = store.get(sink.received[0].id)
    assert stored is not None
    assert stored.enrichments["length"].value == len("b edited")


def test_sink_failure_stores_nothing_and_keeps_cursor(store: Store) -> None:
    source = ListSource(["a", "b"])
    with pytest.raises(PipelineError, match="endpoint down"):
        run(pipeline(source, sinks=[MemorySink(fail=True)]), store)
    assert store.count() == 0
    assert store.get_cursor("daily", "reviews") is None
    sink = MemorySink()
    run(pipeline(source, sinks=[sink]), store)
    assert len(sink.received) == 2


def test_failure_in_later_batch_keeps_earlier_batches(store: Store) -> None:
    class FlakySink(MemorySink):
        def send(self, batch: Sequence[Record]) -> SinkResult:
            self.fail = bool(self.received)
            return super().send(batch)

    with pytest.raises(PipelineError):
        run(pipeline(ListSource(["a", "b", "c"]), sinks=[FlakySink()], batch_size=2), store)
    assert store.count() == 2
    assert store.get_cursor("daily", "reviews") == {"offset": 2}


def test_enricher_must_return_one_result_per_record(store: Store) -> None:
    with pytest.raises(PipelineError, match="returned 0 results"):
        run(pipeline(ListSource(["a"]), enrichers=[BrokenEnricher()]), store)


class OutageEnricher:
    name: ClassVar[str] = "classify"
    version: ClassVar[str] = "1"

    def __init__(self, *, down: bool) -> None:
        self.down = down
        self.last_error: str | None = None

    def enrich(self, batch: Sequence[Record]) -> Sequence[Enrichment | None]:
        if self.down:
            self.last_error = "cannot reach the model at http://llm.internal/v1"
            return [None] * len(batch)
        return [Enrichment(value="ok", at=T0) for _ in batch]


def test_failed_enrichment_is_reported_and_retried_next_run(store: Store) -> None:
    source = ListSource(["a", "b"])
    report = run(pipeline(source, enrichers=[OutageEnricher(down=True)]), store)
    assert report.stored == 2
    assert report.failed == {"classify": 2}
    assert report.errors == {"classify": "cannot reach the model at http://llm.internal/v1"}
    assert all("classify" not in r.enrichments for r in store.iter_records())

    sink = MemorySink()
    report = run(pipeline(source, sinks=[sink], enrichers=[OutageEnricher(down=False)]), store)
    assert report.fetched == 0
    assert report.enriched == {"classify": 2}
    assert report.failed == {}
    assert len(sink.received) == 2
    assert all(r.enrichments["classify"].value == "ok" for r in store.iter_records())

    again = run(pipeline(source, enrichers=[OutageEnricher(down=True)]), store)
    assert again.failed == {}
    assert store.retry_records("daily", "reviews", 10) == []


def test_store_lock_is_free_while_fetching_enriching_and_delivering(store: Store) -> None:
    lock = threading.Lock()
    observed: list[bool] = []

    def lock_free() -> bool:
        free = lock.acquire(blocking=False)
        if free:
            lock.release()
        return free

    class ProbeSource(ListSource):
        def fetch(self, cursor: Cursor | None) -> Iterator[tuple[Record, Cursor]]:
            for item in super().fetch(cursor):
                observed.append(lock_free())
                yield item

    class ProbeEnricher(LengthEnricher):
        def enrich(self, batch: Sequence[Record]) -> Sequence[Enrichment | None]:
            observed.append(lock_free())
            return super().enrich(batch)

    class ProbeSink(MemorySink):
        def send(self, batch: Sequence[Record]) -> SinkResult:
            observed.append(lock_free())
            return super().send(batch)

    probe = pipeline(ProbeSource(["a", "b"]), sinks=[ProbeSink()], enrichers=[ProbeEnricher()])
    assert run(probe, store, lock=lock).stored == 2
    assert observed == [True, True, True, True]


def test_erased_records_are_not_refetched_enriched_or_delivered(store: Store) -> None:
    source = ListSource(["a", "b"], honour_cursor=False)
    run(pipeline(source), store)
    assert store.delete(source_type="list") == 2
    sink, enricher = MemorySink(), LengthEnricher()
    report = run(pipeline(source, sinks=[sink], enrichers=[enricher]), store)
    assert report.fetched == 2
    assert (report.stored, enricher.calls, sink.received) == (0, 0, [])
    assert store.count() == 0
