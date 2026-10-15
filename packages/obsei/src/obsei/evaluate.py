"""Measure the ``classify`` enricher against labelled feedback, and keep human corrections.

A correction overwrites the answer inside the record's ``classify`` enrichment with confidence 1
and lists the question under ``corrected``, so routes, MCP tools and Studio read corrected labels
as they read model labels, and ``obsei reprocess`` keeps them.
"""

from __future__ import annotations

import csv
from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, JsonValue

from obsei.core.protocols import Enricher
from obsei.core.record import Enrichment, Record, SourceRef
from obsei.enrichers.classify import ClassifierConfig, ClassifyPluginConfig
from obsei.pipeline import Redactor
from obsei.routing import answer, flagged

CLASSIFY = "classify"
HUMAN = "human"
TOP_LEVEL = ("sentiment", "intent")
INFO_COLUMNS = frozenset({"id", "text", "lang"})
Options = Mapping[str, list[str] | None]


class Row(BaseModel):
    gold: str
    predicted: str | None
    confidence: float
    lang: str | None = None


class Cutoff(BaseModel):
    cutoff: float
    accuracy: float
    """Of the answers at or above the cutoff."""
    review_rate: float
    """Share of answers below the cutoff."""


class LanguageScore(BaseModel):
    lang: str
    accuracy: float
    n: int


class Confusion(BaseModel):
    gold: str
    predicted: str | None
    count: int


class QuestionReport(BaseModel):
    question: str
    n: int
    accuracy: float
    macro_f1: float
    ece: float
    brier: float
    current: Cutoff
    suggested: Cutoff | None
    worst_language: LanguageScore | None
    confusions: list[Confusion]


class EvalReport(BaseModel):
    model: str | None
    records: int
    failed: int
    review_rate: float
    target_precision: float
    questions: list[QuestionReport]


class Example(BaseModel):
    record: Record
    labels: dict[str, str]


def _accuracy(rows: Sequence[Row]) -> float:
    return sum(r.predicted == r.gold for r in rows) / len(rows) if rows else 0.0


def macro_f1(rows: Sequence[Row]) -> float:
    labels = {r.gold for r in rows} | {r.predicted for r in rows if r.predicted is not None}
    scores = []
    for label in labels:
        tp = sum(r.gold == label and r.predicted == label for r in rows)
        fp = sum(r.gold != label and r.predicted == label for r in rows)
        fn = sum(r.gold == label and r.predicted != label for r in rows)
        scores.append(2 * tp / (2 * tp + fp + fn) if tp else 0.0)
    return sum(scores) / len(scores) if scores else 0.0


def ece(rows: Sequence[Row], bins: int = 10) -> float:
    """Expected calibration error of the confidence, in equal-width bins."""
    error = 0.0
    for b in range(bins):
        low, high = b / bins, (b + 1) / bins
        chosen = [r for r in rows if low < r.confidence <= high or (b == 0 and r.confidence == 0)]
        if chosen:
            mean = sum(r.confidence for r in chosen) / len(chosen)
            error += len(chosen) * abs(_accuracy(chosen) - mean)
    return error / len(rows) if rows else 0.0


def brier(rows: Sequence[Row]) -> float:
    """Of the top answer's confidence against whether it was right."""
    return sum((r.confidence - (r.predicted == r.gold)) ** 2 for r in rows) / len(rows)


def at_cutoff(rows: Sequence[Row], cutoff: float) -> Cutoff:
    kept = [r for r in rows if r.confidence >= cutoff]
    return Cutoff(cutoff=cutoff, accuracy=_accuracy(kept), review_rate=1 - len(kept) / len(rows))


def suggest_cutoff(rows: Sequence[Row], target_precision: float = 0.9) -> Cutoff | None:
    """The lowest cutoff (in steps of 0.01) whose kept answers are right at least
    ``target_precision`` of the time; None when no cutoff reaches it."""
    for step in range(101):
        found = at_cutoff(rows, step / 100)
        if found.review_rate < 1 and found.accuracy >= target_precision:
            return found
    return None


def question_report(
    question: str, rows: Sequence[Row], *, cutoff: float, target_precision: float = 0.9
) -> QuestionReport:
    by_lang: dict[str, list[Row]] = defaultdict(list)
    for row in rows:
        if row.lang:
            by_lang[row.lang].append(row)
    scores = [LanguageScore(lang=k, accuracy=_accuracy(v), n=len(v)) for k, v in by_lang.items()]
    wrong = Counter((r.gold, r.predicted) for r in rows if r.predicted != r.gold)
    return QuestionReport(
        question=question,
        n=len(rows),
        accuracy=_accuracy(rows),
        macro_f1=macro_f1(rows),
        ece=ece(rows),
        brier=brier(rows),
        current=at_cutoff(rows, cutoff),
        suggested=suggest_cutoff(rows, target_precision),
        worst_language=min(scores, key=lambda s: (s.accuracy, s.lang), default=None),
        confusions=[Confusion(gold=g, predicted=p, count=n) for (g, p), n in wrong.most_common(3)],
    )


def questions(config: ClassifierConfig) -> dict[str, list[str] | None]:
    """Each question the classifier answers, with its answers (None for free text)."""
    found: dict[str, list[str] | None] = {
        "sentiment": list(config.sentiments),
        "intent": list(config.intents),
    }
    for name, spec in config.fields.items():
        if spec.kind == "yesno":
            found[name] = ["true", "false"]
        else:
            found[name] = list(spec.choices or spec.levels or []) or None
    return found


def path(question: str) -> str:
    return f"{CLASSIFY}.{question}" if question in TOP_LEVEL else f"{CLASSIFY}.fields.{question}"


def read_labels(
    file: Path, options: Options, key: str
) -> list[tuple[dict[str, str], dict[str, str]]]:
    """(row, labels) of a CSV with a ``key`` column and a column per question, named as in
    ``options``; empty cells are not labelled."""
    with file.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        columns = set(reader.fieldnames or [])
        if key not in columns:
            raise ValueError(f"{file}: no {key!r} column")
        unknown = columns - INFO_COLUMNS - set(options)
        if unknown:
            raise ValueError(
                f"{file}: unknown question columns {sorted(unknown)}; the classifier answers "
                f"{list(options)}"
            )
        rows = []
        for row in reader:
            if not (row.get(key) or "").strip():
                raise ValueError(f"{file}, line {reader.line_num}: empty {key}")
            labels = {q: v for q in options if (v := (row.get(q) or "").strip())}
            for question, label in labels.items():
                allowed = options[question]
                if allowed is not None and label not in allowed:
                    raise ValueError(
                        f"{file}, line {reader.line_num}: {question} {label!r} is not one of "
                        f"{allowed}"
                    )
            rows.append((row, labels))
    return rows


def gold_examples(file: Path, options: Options, redactor: Redactor | None) -> list[Example]:
    """Examples from a gold CSV (``text``, optional ``lang``, a column per question), redacted
    as at ingest."""
    rows = read_labels(file, options, "text")
    now = datetime.now(UTC)
    records = [
        Record(
            source=SourceRef(type="gold", native_id=str(i)),
            text=row["text"],
            created_at=now,
            lang=row.get("lang") or None,
        )
        for i, (row, _) in enumerate(rows)
    ]
    if redactor is not None:
        records = list(redactor.redact(records))
    return [Example(record=r, labels=labels) for r, (_, labels) in zip(records, rows, strict=True)]


def corrections(record: Record) -> dict[str, str]:
    """The human answers of a record, by question."""
    enrichment = record.enrichments.get(CLASSIFY)
    value = enrichment.value if enrichment else None
    corrected = _strings(value.get("corrected")) if isinstance(value, dict) else []
    found = {q: answer(record, path(q))[0] for q in corrected}
    return {q: label for q, label in found.items() if label is not None}


def corrected_examples(records: Iterable[Record]) -> list[Example]:
    return [Example(record=r, labels=labels) for r in records if (labels := corrections(r))]


def _table(value: JsonValue) -> dict[str, JsonValue]:
    return dict(value) if isinstance(value, dict) else {}


def _strings(value: JsonValue) -> list[str]:
    return [v for v in value if isinstance(v, str)] if isinstance(value, list) else []


def correct(enrichment: Enrichment | None, labels: Mapping[str, str]) -> Enrichment:
    """A ``classify`` result with human ``labels`` (by question): confidence 1, no longer
    uncertain, and listed under ``corrected``."""
    old = _table(enrichment.value) if enrichment else {}
    value = dict(old)
    fields, confidences = _table(old.get("fields")), _table(old.get("confidences"))
    probabilities, scores = _table(old.get("probabilities")), _table(old.get("scores"))
    levels = _table(old.get("levels"))
    for question, label in labels.items():
        stored: JsonValue = label == "true" if label in ("true", "false") else label
        if question in TOP_LEVEL:
            value[question] = stored
        else:
            fields[question] = stored
        confidences[question] = 1.0
        probabilities[question] = {label: 1.0}
        known = levels.get(question)
        if isinstance(known, list) and label in known:
            scores[question] = float(known.index(label))
        else:
            scores.pop(question, None)
    uncertain: list[JsonValue] = [q for q in _strings(old.get("uncertain")) if q not in labels]
    value.update(
        fields=fields,
        confidences=confidences,
        probabilities=probabilities,
        scores=scores,
        uncertain=uncertain,
        review=bool(uncertain),
        corrected=list[JsonValue](sorted({*_strings(old.get("corrected")), *labels})),
    )
    numbers = [c for c in confidences.values() if isinstance(c, float)]
    return Enrichment(
        value=value,
        confidence=enrichment.confidence
        if enrichment and "confidences" not in old
        else min(numbers),
        model=enrichment.model if enrichment else HUMAN,
    )


def evaluate(
    classifier: Enricher,
    examples: Sequence[Example],
    config: ClassifyPluginConfig,
    *,
    target_precision: float = 0.9,
) -> EvalReport:
    """Label each example's record afresh and compare with its labels."""
    results = classifier.enrich([e.record for e in examples])
    labelled = [
        e.record.model_copy(update={"enrichments": {CLASSIFY: r} if r else {}})
        for e, r in zip(examples, results, strict=True)
    ]
    reports = []
    for question in questions(config):
        rows = []
        for example, record in zip(examples, labelled, strict=True):
            if question in example.labels:
                predicted, confidence = answer(record, path(question))
                rows.append(
                    Row(
                        gold=example.labels[question],
                        predicted=predicted,
                        confidence=confidence or 0.0,
                        lang=record.lang,
                    )
                )
        if rows:
            cutoff = config.min_confidence.get(question, config.threshold)
            reports.append(
                question_report(question, rows, cutoff=cutoff, target_precision=target_precision)
            )
    return EvalReport(
        model=next((r.model for r in results if r is not None and r.model), None),
        records=len(examples),
        failed=sum(r is None for r in results),
        review_rate=sum(flagged(r) for r in labelled) / len(labelled) if labelled else 0.0,
        target_precision=target_precision,
        questions=reports,
    )
