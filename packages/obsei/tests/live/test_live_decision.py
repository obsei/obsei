"""The decision-routing example against a real decision model. Opt in by setting
OBSEI_DECISION_URL to the decision endpoint your server documents (e.g. llama.cpp serving
``ggml-org/Julia-1-GGUF``).

Answers are model-dependent, so this checks the contract: every answer is one of the configured
options, with probabilities, and the run completes."""

import os
from pathlib import Path
from typing import Any

import pytest

from obsei.config import build_context, build_pipeline, load_config
from obsei.core.context import LlmEndpoint
from obsei.core.protocols import Drops
from obsei.pipeline import run
from obsei.store import Query, Store

URL = os.environ.get("OBSEI_DECISION_URL")
ROOT = Path(__file__).resolve().parents[4]
pytestmark = pytest.mark.skipif(not URL, reason="set OBSEI_DECISION_URL to a decision endpoint")


def test_decision_routing_sample(monkeypatch: pytest.MonkeyPatch) -> None:
    assert URL is not None
    monkeypatch.chdir(ROOT)
    monkeypatch.setenv("OBSEI_PSEUDONYM_SALT", "live-test-salt-0123456789")
    config = load_config(ROOT / "examples" / "decision-routing.yaml")
    julia = LlmEndpoint(api="decision", url_env="OBSEI_DECISION_URL")
    assert config.llms["julia"].url_env == "OBSEI_DECISION_URL"
    config = config.model_copy(update={"llms": {"julia": julia}, "ask_judge": None})
    for spec in config.pipelines:
        for enricher in spec.enrichers:
            enricher.config.pop("fallback_llm", None)
    with build_context(config) as ctx:
        pipeline = build_pipeline(config, "sample", ctx, with_sinks=False)
        spam_filter = pipeline.enrichers[0]
        assert isinstance(spam_filter, Drops)
        store = Store(allow_unencrypted=True)
        report = run(pipeline, store)
    assert report.fetched == 8
    assert report.stored + sum(report.dropped.values()) == 8
    assert report.failed == {}
    options: Any = config.pipelines[1].enrichers[1].config
    for record in store.search(Query(), limit=20):
        value: Any = record.enrichments["classify"].value
        assert value["intent"] in options["intents"]
        assert value["sentiment"] in options["sentiments"]
        assert value["fields"]["urgency"] in options["fields"]["urgency"]["levels"]
        assert isinstance(value["fields"]["asks_for_refund"], bool)
        assert sum(value["probabilities"]["intent"].values()) == pytest.approx(1, abs=0.01)
