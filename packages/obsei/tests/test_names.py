import os
from datetime import UTC, datetime

import pytest

from obsei import Record, SourceRef
from obsei.llm import EgressPolicy
from obsei.privacy.names import (
    GlinerDetector,
    NameRedactionError,
    NameRedactor,
    NamesConfig,
    Span,
    chunks,
    mask,
    redactor_for,
)
from obsei.privacy.redact import RegexRedactor

NAMES = [
    "María García",
    "田中太郎",
    "राहुल शर्मा",
    "Jean-Pierre Dubois",
    "Olúwaseun Adé",
    "Ахмед Ильин",
]
SAMPLES = [
    (
        "es",
        "Hola, soy María García y la app falla al pagar.",
        "Hola, soy <PERSON> y la app falla al pagar.",
    ),
    ("ja", "田中太郎です。ログインできません。", "<PERSON>です。ログインできません。"),
    ("hi", "मैं राहुल शर्मा हूँ, ऐप बहुत धीमा है।", "मैं <PERSON> हूँ, ऐप बहुत धीमा है।"),
    (
        "fr",
        "Bonjour, Jean-Pierre Dubois ici : remboursement SVP.",
        "Bonjour, <PERSON> ici : remboursement SVP.",
    ),
    ("yo", "Olúwaseun Adé says the update broke sync.", "<PERSON> says the update broke sync."),
    ("ru", "Ахмед Ильин: приложение вылетает.", "<PERSON>: приложение вылетает."),
]


class ListDetector:
    def __init__(self, names: list[str]) -> None:
        self.names = names

    def detect(self, text: str) -> list[Span]:
        spans: list[Span] = []
        for name in self.names:
            start = text.find(name)
            while start != -1:
                spans.append({"start": start, "end": start + len(name)})
                start = text.find(name, start + 1)
        return spans


def record(text: str, context: dict[str, str] | None = None) -> Record:
    return Record(
        source=SourceRef(type="csv", native_id="1"),
        text=text,
        created_at=datetime(2026, 9, 1, tzinfo=UTC),
        context=context or {},
    )


@pytest.mark.parametrize(("lang", "text", "expected"), SAMPLES)
def test_names_replaced_in_any_script(lang: str, text: str, expected: str) -> None:
    (out,) = NameRedactor(ListDetector(NAMES)).redact([record(text)])
    assert out.text == expected, lang


def test_overlapping_spans_merge() -> None:
    spans: list[Span] = [{"start": 0, "end": 5}, {"start": 3, "end": 9}, {"start": 12, "end": 14}]
    assert mask("abcdefghijklmnop", spans) == "<PERSON>jkl<PERSON>op"


def test_chunks_keep_offsets_for_long_text() -> None:
    text = ("Sentence number one is here. " * 60) + "Ana Lima wrote this."
    pieces = chunks(text, size=200)
    assert all(len(piece) <= 200 for _, piece in pieces)
    assert all(text[offset : offset + len(piece)] == piece for offset, piece in pieces)
    assert any("Ana Lima" in piece for _, piece in pieces)


def test_regex_then_names_and_context() -> None:
    chain = redactor_for(["global"], NamesConfig(), EgressPolicy())
    assert isinstance(chain, RegexRedactor)
    redactor = NameRedactor(ListDetector(["María García"]))
    (out,) = redactor.redact(
        RegexRedactor().redact(
            [record("María García, maria@example.es", {"subject": "De María García"})]
        )
    )
    assert out.text == "<PERSON>, <EMAIL>"
    assert out.context == {"subject": "De <PERSON>"}


def test_air_gapped_requires_a_local_model() -> None:
    with pytest.raises(NameRedactionError, match="air-gapped"):
        GlinerDetector(NamesConfig(enabled=True), EgressPolicy())


@pytest.mark.skipif(
    not os.environ.get("OBSEI_LIVE"), reason="set OBSEI_LIVE=1 to download and run GLiNER"
)
def test_gliner_finds_names_in_several_languages() -> None:
    pytest.importorskip("gliner")
    detector = GlinerDetector(NamesConfig(enabled=True), EgressPolicy(mode="hybrid"))
    redactor = NameRedactor(detector)
    missed = [
        lang
        for lang, text, _ in SAMPLES
        if any(name in redactor.redact([record(text)])[0].text for name in NAMES)
    ]
    assert len(missed) <= 1, f"names left in: {missed}"
