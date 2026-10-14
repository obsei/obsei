import os
import sys
import time
import types
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError
from typer.testing import CliRunner

from obsei import Record, SourceRef
from obsei.cli import app
from obsei.core.context import Context, LlmEndpoint
from obsei.demo import DECISION_CONFIG, redacted_demo_records
from obsei.enrichers import Cascade, ClassifyPluginConfig
from obsei.enrichers.classify import LocalClassifier, build_classifier
from obsei.llm import EgressPolicy, LlmError, local
from obsei.llm.local import LOCAL_CLASSIFIER, Options, Scorer

GLINER = "fastino/gliner2-multi-v1"
CLASSIFY: dict[str, Any] = {
    "llm": "local",
    "intents": {"bug": "something is broken", "billing": "charges and refunds"},
    "fields": {
        "urgency": {
            "description": "How urgent is this?",
            "levels": ["can wait", "this week", "today", "right now"],
        },
        "angry": {
            "type": "yesno",
            "description": "Is the customer angry?",
            "yes_means": "angry or furious",
            "no_means": "calm",
        },
    },
    "min_confidence": {"urgency": 0.25},
}


class Models:
    """Fake zero-shot models: an option named in the text gets 0.85, the rest share 0.15."""

    def __init__(self) -> None:
        self.loaded: list[tuple[str, bool]] = []
        self.asked: list[tuple[str, str, Options]] = []

    def load(self, model: str, offline: bool) -> Scorer:
        self.loaded.append((model, offline))

        def score(text: str, options: Options) -> dict[str, float]:
            self.asked.append((model, text, options))
            hit = next((k for k in options if k in text), None)
            if hit is None:
                return dict.fromkeys(options, 1 / len(options))
            rest = 0.15 / (len(options) - 1)
            return {k: 0.85 if k == hit else rest for k in options}

        return score


@pytest.fixture
def models(monkeypatch: pytest.MonkeyPatch) -> Models:
    fake = Models()
    monkeypatch.setattr(local, "load", fake.load)
    return fake


def _module(name: str, **attrs: Any) -> types.ModuleType:
    module = types.ModuleType(name)
    module.__dict__.update(attrs)
    return module


def rec(text: str, native_id: str = "1") -> Record:
    return Record(
        source=SourceRef(type="zendesk", native_id=native_id),
        text=text,
        created_at=datetime(2026, 9, 1, tzinfo=UTC),
        rating=1,
        lang="en",
    )


def _ctx(egress: EgressPolicy | None = None, **endpoint: Any) -> Context:
    return Context(
        egress=egress or EgressPolicy(), llms={"local": LlmEndpoint(api="local", **endpoint)}
    )


def test_local_classifier_answers_every_question_in_process(models: Models) -> None:
    config = ClassifyPluginConfig.model_validate(CLASSIFY)
    classifier = build_classifier(config, _ctx(models={"sentiment": GLINER}))
    assert isinstance(classifier, LocalClassifier)
    assert sorted(models.loaded) == [(LOCAL_CLASSIFIER, True), (GLINER, True)]
    assert classifier.client.model == f"{LOCAL_CLASSIFIER}, sentiment: {GLINER}"

    sure, unsure = classifier.enrich([rec("billing, negative, right now, yes"), rec("hmm", "2")])

    assert {text for _, text, _ in models.asked} == {"billing, negative, right now, yes", "hmm"}
    by_model = {tuple(options): model for model, _, options in models.asked}
    assert by_model[("positive", "negative", "neutral", "mixed")] == GLINER
    assert by_model[("bug", "billing")] == LOCAL_CLASSIFIER
    urgency = next(o for _, _, o in models.asked if "today" in o)
    assert urgency["today"] == "How urgent is this?"

    assert sure is not None
    value: Any = sure.value
    assert (value["sentiment"], value["intent"]) == ("negative", "billing")
    assert value["fields"] == {"urgency": "right now", "angry": True}
    assert value["scores"]["urgency"] == pytest.approx(2.7)
    assert value["probabilities"]["angry"] == {"true": 0.85, "false": pytest.approx(0.15)}
    assert value["levels"]["urgency"][-1] == "right now"
    assert value["review"] is False
    assert sure.confidence == pytest.approx(0.85)

    assert unsure is not None
    assert isinstance(unsure.value, dict)
    assert unsure.value["review"] is True
    assert unsure.value["uncertain"] == ["sentiment", "intent", "angry"]


def test_low_confidence_escalates_to_the_fallback(models: Models) -> None:
    llms = {
        "local": LlmEndpoint(api="local"),
        "chat": LlmEndpoint(base_url="http://localhost:11434/v1", model="m"),
    }
    config = ClassifyPluginConfig.model_validate({**CLASSIFY, "fallback_llm": "chat"})
    classifier = build_classifier(config, Context(llms=llms))
    assert isinstance(classifier, Cascade)
    assert classifier.threshold is None


def test_local_endpoint_shape_and_config_errors(models: Models) -> None:
    with pytest.raises(ValidationError, match="not a URL"):
        LlmEndpoint(api="local", url="http://decide.internal/x")
    with pytest.raises(ValidationError, match="models is for local endpoints"):
        LlmEndpoint(base_url="http://localhost:11434/v1", model="m", models={"sentiment": "x"})
    ctx = _ctx(egress=EgressPolicy(mode="hybrid"), model="org/nli")
    with pytest.raises(KeyError, match="local model, not a chat model"):
        ctx.chat("local")
    with pytest.raises(KeyError, match="api: decision"):
        ctx.decision("local")
    bare = {"llm": "local", "fields": {"angry": {"type": "yesno", "description": "Angry?"}}}
    with pytest.raises(ValueError, match="yes_means and no_means"):
        build_classifier(ClassifyPluginConfig.model_validate(bare), ctx)
    assert models.loaded == []
    ctx.local("local")
    assert models.loaded == [("org/nli", False)]


def test_nli_and_gliner2_adapters(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[dict[str, Any]] = []

    def pipeline(task: str, model: str, device: int) -> Any:
        def classify(text: str, labels: list[str], **kw: Any) -> dict[str, list[Any]]:
            calls.append({"task": task, "model": model, "labels": labels, **kw})
            return {"labels": labels[::-1], "scores": [0.3, 0.7]}

        return classify

    class GLiNER2:
        @classmethod
        def from_pretrained(cls, path: str) -> "GLiNER2":
            return cls()

        def classify_text(self, text: str, tasks: dict[str, Any], **kw: Any) -> dict[str, Any]:
            calls.append({"tasks": tasks, **kw})
            return {"q": [{"label": "yes", "confidence": 0.9}, {"label": "no", "confidence": 0.1}]}

    monkeypatch.setitem(sys.modules, "transformers", _module("transformers", pipeline=pipeline))
    monkeypatch.setitem(sys.modules, "gliner2", _module("gliner2", GLiNER2=GLiNER2))
    options = {"yes": "angry", "no": None}
    assert local._nli("/models/nli")("text", options) == {"yes": 0.7, "no": 0.3}
    assert calls[-1] == {
        "task": "zero-shot-classification",
        "model": "/models/nli",
        "labels": ["yes: angry", "no"],
        "hypothesis_template": "This customer message is {}",
        "multi_label": False,
    }
    assert local._gliner2("/models/g")("text", options) == {"yes": 0.9, "no": 0.1}
    assert calls[-1]["tasks"]["q"]["labels"] == {"yes": "angry", "no": "no"}
    assert calls[-1]["include_confidence"] is True


def test_fetch_respects_offline_and_explains_install(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    seen: list[dict[str, Any]] = []

    def snapshot_download(model: str, cache_dir: str | None, local_files_only: bool) -> str:
        seen.append({"model": model, "cache_dir": cache_dir, "offline": local_files_only})
        if local_files_only:
            raise FileNotFoundError("not in cache")
        return "/models/snapshot"

    hub = _module("huggingface_hub", snapshot_download=snapshot_download)
    monkeypatch.setitem(sys.modules, "huggingface_hub", hub)
    monkeypatch.setenv("OBSEI_MODELS_DIR", "/models")
    assert local.fetch("org/nli", offline=False) == "/models/snapshot"
    assert seen == [{"model": "org/nli", "cache_dir": "/models", "offline": False}]
    with pytest.raises(LlmError, match="obsei models download --classifier org/nli"):
        local.fetch("org/nli", offline=True)
    assert local.fetch(str(tmp_path), offline=True) == str(tmp_path)

    monkeypatch.setitem(sys.modules, "huggingface_hub", None)
    with pytest.raises(LlmError, match=r"obsei\[local\]"):
        local.fetch("org/nli", offline=False)


def test_models_download_fetches_the_classifier(monkeypatch: pytest.MonkeyPatch) -> None:
    fetched: list[tuple[str, str | None]] = []
    monkeypatch.setattr(
        "obsei.cli.fetch", lambda m, *, offline, cache_dir: fetched.append((m, cache_dir))
    )
    monkeypatch.setattr("obsei.cli.find_spec", lambda name: name == "gliner2")
    result = CliRunner().invoke(app, ["models", "download", "--dir", "/models"])
    assert result.exit_code == 0, result.output
    assert fetched == [(LOCAL_CLASSIFIER, str(Path("/models")))]

    monkeypatch.setattr("obsei.cli.find_spec", lambda name: False)
    result = CliRunner().invoke(app, ["models", "download"])
    assert result.exit_code != 0
    assert "nothing to download" in result.output


@pytest.mark.skipif(
    not os.environ.get("OBSEI_LOCAL_MODELS"),
    reason="set OBSEI_LOCAL_MODELS=1 to download and run the local models",
)
def test_real_models_label_demo_records() -> None:
    pytest.importorskip("gliner2")
    wanted = {
        "login-en-0": ("bug", "negative", "engineering"),
        "billing-en-0": ("complaint", "negative", "payments"),
        "delivery-en-0": ("complaint", "negative", "logistics"),
    }
    records = [r for r in redacted_demo_records() if r.source.native_id in wanted]
    ctx = Context(
        egress=EgressPolicy(mode="hybrid"),
        llms={"default": LlmEndpoint(api="local", models={"sentiment": GLINER})},
    )
    config = ClassifyPluginConfig.model_validate(DECISION_CONFIG.model_dump())
    classifier = build_classifier(config, ctx)
    start = time.perf_counter()
    results = classifier.enrich(records)
    print(f"{len(records) / (time.perf_counter() - start):.2f} records/s")
    for record, result in zip(records, results, strict=True):
        assert result is not None
        value: Any = result.value
        got = (value["intent"], value["sentiment"], value["fields"]["team"])
        assert got == wanted[record.source.native_id]
        assert value["fields"]["urgency"] in ["can wait", "this week", "today", "right now"]
