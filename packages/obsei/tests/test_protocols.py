from collections.abc import Iterator, Sequence
from datetime import UTC, datetime
from typing import ClassVar

from obsei import Enrichment, Record, SourceRef
from obsei.core.protocols import Cursor, Enricher, Sink, SinkResult, Source


class ListSource:
    name: ClassVar[str] = "list"

    def __init__(self, texts: list[str]) -> None:
        self.texts = texts

    def fetch(self, cursor: Cursor | None) -> Iterator[tuple[Record, Cursor]]:
        start = int((cursor or {}).get("offset") or 0)
        for i, text in enumerate(self.texts[start:], start=start):
            record = Record(
                source=SourceRef(type=self.name, native_id=str(i)),
                text=text,
                created_at=datetime(2026, 1, 1, tzinfo=UTC),
            )
            yield record, {"offset": i + 1}


class LengthEnricher:
    name: ClassVar[str] = "length"
    version: ClassVar[str] = "1"

    def enrich(self, batch: Sequence[Record]) -> Sequence[Enrichment | None]:
        return [Enrichment(value=len(r.text), model="len") for r in batch]


class MemorySink:
    name: ClassVar[str] = "memory"

    def __init__(self) -> None:
        self.items: dict[str, Record] = {}

    def send(self, batch: Sequence[Record]) -> SinkResult:
        new = [r for r in batch if r.id not in self.items]
        self.items.update({r.id: r for r in new})
        return SinkResult(sent=len(new), skipped=len(batch) - len(new))


def test_minimal_plugins_satisfy_protocols_and_compose() -> None:
    source, enricher, sink = ListSource(["a", "bb"]), LengthEnricher(), MemorySink()
    assert isinstance(source, Source)
    assert isinstance(enricher, Enricher)
    assert isinstance(sink, Sink)

    records = [r for r, _ in source.fetch({"offset": 0})]
    enriched = [
        r.with_enrichment(enricher.name, e)
        for r, e in zip(records, enricher.enrich(records), strict=True)
        if e is not None
    ]
    assert sink.send(enriched) == SinkResult(sent=2)
    assert sink.send(enriched) == SinkResult(skipped=2)  # idempotent by Record.id
    assert [r.enrichments["length"].value for r in sink.items.values()] == [1, 2]


def test_cursor_resumes() -> None:
    cursors = [c for _, c in ListSource(["a", "b", "c"]).fetch({"offset": 1})]
    assert cursors == [{"offset": 2}, {"offset": 3}]
