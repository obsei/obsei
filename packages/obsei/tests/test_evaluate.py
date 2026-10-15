import csv
import json
from collections.abc import Mapping
from datetime import UTC, datetime
from importlib import resources
from pathlib import Path

import pytest
from typer.testing import CliRunner

from obsei import Record, SourceRef
from obsei.cli import app
from obsei.core.record import Enrichment
from obsei.demo import GOLD_CONFIG, GOLD_FILE, ISSUES
from obsei.evaluate import (
    Row,
    at_cutoff,
    brier,
    correct,
    corrections,
    ece,
    macro_f1,
    question_report,
    questions,
    read_labels,
    suggest_cutoff,
)
from obsei.llm import local
from obsei.llm.local import Options
from obsei.routing import When
from obsei.store import Store

runner = CliRunner()
ROWS = [
    Row(gold="a", predicted="a", confidence=0.9, lang="en"),
    Row(gold="a", predicted="b", confidence=0.8, lang="en"),
    Row(gold="b", predicted="b", confidence=0.6, lang="ja"),
    Row(gold="b", predicted="b", confidence=0.3, lang="ja"),
]


def test_metrics_match_hand_computed_values() -> None:
    assert macro_f1(ROWS) == pytest.approx((2 / 3 + 4 / 5) / 2)
    assert ece(ROWS) == pytest.approx((0.7 + 0.4 + 0.8 + 0.1) / 4)
    assert brier(ROWS) == pytest.approx((0.01 + 0.64 + 0.16 + 0.49) / 4)
    half = at_cutoff(ROWS, 0.5)
    assert half.accuracy == pytest.approx(2 / 3)
    assert half.review_rate == 0.25
    report = question_report("intent", ROWS, cutoff=0.5)
    assert report.accuracy == 0.75
    assert report.worst_language is not None
    assert (report.worst_language.lang, report.worst_language.accuracy) == ("en", 0.5)
    assert [(c.gold, c.predicted, c.count) for c in report.confusions] == [("a", "b", 1)]


def test_suggest_cutoff_is_the_lowest_that_reaches_the_target() -> None:
    strict = suggest_cutoff(ROWS, 0.9)
    assert strict is not None
    assert (strict.cutoff, strict.accuracy, strict.review_rate) == (0.81, 1.0, 0.75)
    loose = suggest_cutoff(ROWS, 0.7)
    assert loose is not None
    assert (loose.cutoff, loose.review_rate) == (0.0, 0.0)
    assert suggest_cutoff([Row(gold="a", predicted="b", confidence=1.0)]) is None


def _record(text: str, native_id: str, value: Mapping[str, object] | None = None) -> Record:
    record = Record(
        source=SourceRef(type="zendesk", native_id=native_id),
        text=text,
        created_at=datetime(2026, 9, 1, tzinfo=UTC),
        lang="en",
    )
    if value is None:
        return record
    return record.with_enrichment(
        "classify", Enrichment.model_validate({"value": value, "confidence": 0.3, "model": "m"})
    )


DECIDED = {
    "sentiment": "negative",
    "intent": "praise",
    "fields": {"team": "mobile", "urgency": "today"},
    "confidences": {"sentiment": 0.9, "intent": 0.4, "team": 0.3, "urgency": 0.5},
    "probabilities": {"team": {"web": 0.3, "mobile": 0.7}},
    "scores": {"urgency": 2.3},
    "levels": {"urgency": ["can wait", "this week", "today", "right now"]},
    "review": True,
    "uncertain": ["intent", "team"],
}


def test_correct_overrides_answers_for_routes_and_keeps_the_rest() -> None:
    record = _record("x", "1", DECIDED)
    fixed = correct(record.enrichments["classify"], {"team": "web", "urgency": "right now"})
    corrected = record.with_enrichment("classify", fixed)
    value = fixed.value
    assert isinstance(value, dict)
    assert value["fields"] == {"team": "web", "urgency": "right now"}
    assert value["scores"] == {"urgency": 3.0}
    assert (value["uncertain"], value["review"]) == (["intent"], True)
    assert value["corrected"] == ["team", "urgency"]
    assert (fixed.confidence, fixed.model) == (0.4, "m")
    when = When.parse({"classify.fields.team": {"is": "web", "min_confidence": 0.99}})
    assert when.matches(corrected)
    assert corrections(corrected) == {"team": "web", "urgency": "right now"}
    human = correct(None, {"intent": "bug"})
    assert (human.model, human.confidence) == ("human", 1.0)


def _write(path: Path, rows: list[list[str]]) -> Path:
    with path.open("w", encoding="utf-8", newline="") as f:
        csv.writer(f).writerows(rows)
    return path


@pytest.fixture
def seen(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Fake local models: an option named in the text gets 0.85, the rest share 0.15."""
    texts: list[str] = []

    def load(model: str, offline: bool) -> local.Scorer:
        def score(text: str, options: Options) -> dict[str, float]:
            texts.append(text)
            hit = next((k for k in options if k in text), None)
            if hit is None:
                return dict.fromkeys(options, 1 / len(options))
            return {k: 0.85 if k == hit else 0.15 / (len(options) - 1) for k in options}

        return score

    monkeypatch.setattr(local, "load", load)
    return texts


CONFIG = """\
version: 1
store: {unencrypted: true}
llms: {default: {api: local}}
pipelines:
  - name: feedback
    sources: [{key: s, type: csv, config: {path: feedback.csv}}]
    enrichers:
      - type: classify
        config:
          intents: [bug, praise]
          threshold: 0.6
          fields: {team: {description: "Which team?", choices: [web, mobile]}}
"""


@pytest.fixture
def project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.delenv("OBSEI_DB_KEY", raising=False)
    (tmp_path / "obsei.yaml").write_text(CONFIG, encoding="utf-8")
    return tmp_path


def _args(project: Path) -> list[str]:
    return ["-c", str(project / "obsei.yaml"), "--db", str(project / "obsei.duckdb")]


def test_eval_scores_the_classifier_on_redacted_gold(project: Path, seen: list[str]) -> None:
    gold = _write(
        project / "gold.csv",
        [
            ["text", "lang", "intent", "sentiment", "team"],
            ["the bug on web, mail me at a.b@example.com", "en", "bug", "", "web"],
            ["praise for mobile, positive", "de", "praise", "positive", "mobile"],
            ["a bug on mobile", "de", "praise", "", "mobile"],
        ],
    )
    config = ["-c", str(project / "obsei.yaml")]
    result = runner.invoke(app, ["eval", str(gold), *config, "--json"])
    assert result.exit_code == 0, result.output
    report = json.loads(result.output)
    by_question = {q["question"]: q for q in report["questions"]}
    assert list(by_question) == ["sentiment", "intent", "team"]
    intent = by_question["intent"]
    assert (intent["n"], intent["accuracy"]) == (3, pytest.approx(2 / 3))
    assert intent["suggested"] is None
    assert intent["confusions"] == [{"gold": "praise", "predicted": "bug", "count": 1}]
    assert by_question["team"]["suggested"]["cutoff"] == 0.0
    assert by_question["sentiment"]["n"] == 1
    assert not any("a.b@example.com" in text for text in seen)
    assert any("<EMAIL>" in text for text in seen)

    table = runner.invoke(app, ["eval", str(gold), *config])
    assert "intent      praise -> bug (1)" in table.output
    gated = runner.invoke(app, ["eval", str(gold), *config, "--min-accuracy", "0.9"])
    assert gated.exit_code == 1


def test_eval_rejects_unknown_questions_and_labels(project: Path, seen: list[str]) -> None:
    config = ["-c", str(project / "obsei.yaml")]
    typo = _write(project / "typo.csv", [["text", "teams"], ["x", "web"]])
    result = runner.invoke(app, ["eval", str(typo), *config])
    assert result.exit_code == 2
    assert "unknown question columns ['teams']" in result.output
    label = _write(project / "label.csv", [["text", "team"], ["x", "ios"]])
    result = runner.invoke(app, ["eval", str(label), *config])
    assert result.exit_code == 2
    assert "team 'ios' is not one of" in result.output
    assert runner.invoke(app, ["eval", *config]).exit_code == 2


def test_eval_demo_runs_the_shipped_gold_set(seen: list[str]) -> None:
    result = runner.invoke(app, ["eval", "--demo", "--json"])
    assert result.exit_code == 0, result.output
    report = json.loads(result.output)
    assert report["records"] == 136
    assert [q["question"] for q in report["questions"]] == ["sentiment", "intent", "team"]


def test_demo_gold_set_matches_the_demo_issues() -> None:
    expected = {
        "login": ("bug", "negative", "engineering"),
        "performance": ("bug", "negative", "engineering"),
        "checkout": ("bug", "negative", "payments"),
        "billing": ("complaint", "negative", "payments"),
        "delivery": ("complaint", "negative", "logistics"),
        "dark_mode": ("feature_request", "neutral", "design"),
        "praise": ("praise", "positive", "design"),
        "support": ("praise", "positive", "support"),
    }
    rows = [
        {"text": t, "lang": g.lang, "intent": i, "sentiment": s, "team": team}
        for key, issue in ISSUES.items()
        for g in issue.groups
        for t in g.texts
        for i, s, team in [expected[key]]
    ]
    with resources.as_file(resources.files("obsei") / "templates" / GOLD_FILE) as file:
        assert [row for row, _ in read_labels(file, questions(GOLD_CONFIG), "text")] == rows


def _seed(project: Path) -> list[Record]:
    old = {"sentiment": "neutral", "intent": "praise", "fields": {"team": "web"}}
    records = [
        _record("a bug on mobile", "1", old),
        _record("a bug on web", "2", old),
        _record("praise for web", "3", old),
        _record("not labelled yet", "4"),
    ]
    with Store(project / "obsei.duckdb", allow_unencrypted=True) as store:
        store.upsert(records)
    return records


def test_reprocess_relabels_and_reports_changes(project: Path, seen: list[str]) -> None:
    records = _seed(project)
    args = _args(project)
    dry = runner.invoke(app, ["reprocess", *args, "--dry-run"])
    assert dry.exit_code == 0, dry.output
    assert "relabelled 3 record(s) (dry run: nothing written)" in dry.output
    assert "intent          2 changed: praise -> bug (2)" in dry.output
    assert "team            1 changed: web -> mobile (1)" in dry.output
    with Store(project / "obsei.duckdb", allow_unencrypted=True, read_only=True) as store:
        unchanged = store.get(records[0].id)
        assert unchanged is not None
        assert unchanged.enrichments == records[0].enrichments

    result = runner.invoke(app, ["reprocess", *args])
    assert result.exit_code == 0, result.output
    with Store(project / "obsei.duckdb", allow_unencrypted=True, read_only=True) as store:
        first, fourth = store.get(records[0].id), store.get(records[3].id)
        assert first is not None
        assert fourth is not None
        value = first.enrichments["classify"].value
        assert isinstance(value, dict)
        assert (value["intent"], value["fields"]) == ("bug", {"team": "mobile"})
        assert "classify" not in fourth.enrichments
        assert any(action == "reprocess" for _, action, _ in store.audit_log())


def test_corrections_survive_reprocess_and_feed_eval(project: Path, seen: list[str]) -> None:
    records = _seed(project)
    args = _args(project)
    labels = _write(
        project / "labels.csv",
        [["id", "intent", "team"], [records[0].id, "praise", ""], [records[1].id, "bug", "web"]],
    )
    result = runner.invoke(app, ["correct", str(labels), *args])
    assert result.exit_code == 0, result.output
    assert "corrected 2 record(s)" in result.output

    runner.invoke(app, ["reprocess", *args])
    with Store(project / "obsei.duckdb", allow_unencrypted=True, read_only=True) as store:
        kept = store.get(records[0].id)
        assert kept is not None
        assert corrections(kept) == {"intent": "praise"}
        assert any(action == "correct" for _, action, _ in store.audit_log())

    result = runner.invoke(app, ["eval", "--from-store", *args, "--json"])
    assert result.exit_code == 0, result.output
    report = json.loads(result.output)
    by_question = {q["question"]: q for q in report["questions"]}
    assert report["records"] == 2
    assert (by_question["intent"]["n"], by_question["intent"]["accuracy"]) == (2, 0.5)
    assert (by_question["team"]["n"], by_question["team"]["accuracy"]) == (1, 1.0)
