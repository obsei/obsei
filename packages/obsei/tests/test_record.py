from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from obsei import Author, Enrichment, Record, SourceRef
from obsei.core.record import normalize_text

NOW = datetime(2026, 10, 1, 12, 0, tzinfo=UTC)


def make(text: str = "Checkout fails on iOS 18", native_id: str = "r1") -> Record:
    return Record(source=SourceRef(type="appstore", native_id=native_id), text=text, created_at=NOW)


def test_id_is_stable_and_derived_from_source() -> None:
    assert make().id == make(text="different text").id
    assert make(native_id="r1").id != make(native_id="r2").id
    assert make().id.startswith("rec_")


def test_content_hash_ignores_case_and_whitespace() -> None:
    assert make("Checkout  fails").content_hash == make("checkout fails").content_hash
    assert make("Checkout fails").content_hash != make("Checkout works").content_hash


def test_normalize_text() -> None:
    assert normalize_text("  \uff26\uff55\uff4c\uff4c\twidth\nTEXT ") == "full width text"


def test_naive_timestamp_rejected() -> None:
    with pytest.raises(ValidationError, match="timezone-aware"):
        Record(
            source=SourceRef(type="csv", native_id="1"),
            text="x",
            created_at=datetime(2026, 1, 1),
        )


def test_author_requires_pseudonym_format() -> None:
    with pytest.raises(ValidationError):
        Author(pseudonym="@real_handle")
    Author(pseudonym="psn_" + "a" * 32)


def test_with_enrichment_returns_copy() -> None:
    record = make()
    enriched = record.with_enrichment("sentiment", Enrichment(value="negative", confidence=0.9))
    assert record.enrichments == {}
    assert enriched.enrichments["sentiment"].value == "negative"
    assert enriched.id == record.id


def test_confidence_bounds() -> None:
    with pytest.raises(ValidationError):
        Enrichment(value="x", confidence=1.5)


def test_extra_fields_forbidden() -> None:
    with pytest.raises(ValidationError):
        Record(
            source=SourceRef(type="csv", native_id="1"),
            text="x",
            created_at=NOW,
            avatar_url="https://example.com/a.png",  # type: ignore[call-arg]
        )


def test_round_trip_json() -> None:
    record = make()
    assert Record.model_validate_json(record.model_dump_json()) == record


def test_explicit_id_is_validated() -> None:
    with pytest.raises(ValidationError, match="rec_"):
        Record(source=SourceRef(type="csv", native_id="1"), text="x", created_at=NOW, id="bad")
