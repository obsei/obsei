import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
import pytest
from pydantic import JsonValue

from obsei.config import builtin_registry, load_config
from obsei.core.context import Context
from obsei.core.protocols import Sink
from obsei.core.record import Enrichment, Record, SourceRef
from obsei.core.registry import Registry
from obsei.llm.egress import EgressError, EgressPolicy
from obsei.sinks._common import SinkConfigError
from obsei_teams import CARD_TYPE, register

EXAMPLE = Path(__file__).parents[3] / "examples" / "alerts-teams.yaml"
URL = "https://prod-01.westeurope.logic.azure.com/workflows/abc/triggers/manual/paths/invoke?sig=s"
ALLOW = EgressPolicy(mode="private", allowed_hosts=frozenset({"logic.azure.com"}))


def record(
    native_id: str,
    text: str,
    *,
    rating: float | None = None,
    url: str | None = None,
    sentiment: str | None = None,
) -> Record:
    item = Record(
        source=SourceRef(type="appstore", instance="us", native_id=native_id, url=url),
        text=text,
        created_at=datetime(2026, 9, 1, tzinfo=UTC),
        rating=rating,
    )
    if sentiment:
        value = {"sentiment": sentiment, "intent": "bug"}
        item = item.with_enrichment("classify", Enrichment(value=value))
    return item


class Hook:
    def __init__(self, status: int = 202) -> None:
        self.status = status
        self.requests: list[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        return httpx.Response(self.status)

    def card(self, index: int = 0) -> Any:
        message = json.loads(self.requests[index].content)
        assert message["type"] == "message"
        (attachment,) = message["attachments"]
        assert attachment["contentType"] == CARD_TYPE
        return attachment["content"]


def sink(hook: Hook, egress: EgressPolicy = ALLOW, **config: JsonValue) -> Sink:
    registry = Registry()
    register(registry)
    ctx = Context(http=httpx.Client(transport=httpx.MockTransport(hook)), egress=egress)
    return registry.sink("teams").create(config, ctx)


@pytest.fixture(autouse=True)
def webhook(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TEAMS_WEBHOOK_URL", URL)


def test_posts_one_adaptive_card_per_batch() -> None:
    hook = Hook()
    teams = sink(hook, title="Negative reviews", when={"classify.sentiment": ["negative"]})
    batch = [
        record(
            "1",
            "Crashes on login",
            rating=1,
            url="https://apps.apple.com/r/1",
            sentiment="negative",
        ),
        record(
            "2",
            "[click](https://evil.example) " + "x" * 700,
            sentiment="negative",
            url="javascript:alert(1)",
        ),
        record("3", "Love it", rating=5, sentiment="positive"),
    ]
    result = teams.send(batch)
    assert (result.sent, result.skipped, result.errors) == (2, 1, [])
    (request,) = hook.requests
    assert request.extensions["obsei_egress"] is True
    content = hook.card()
    assert content["type"] == "AdaptiveCard"
    title, first, second = content["body"]
    assert title["text"] == "Negative reviews"
    head, text, actions = first["items"]
    assert head["text"] == "appstore/us · ★ · negative · bug"
    assert text == {
        "type": "RichTextBlock",
        "inlines": [{"type": "TextRun", "text": "Crashes on login"}],
    }
    assert actions["actions"][0] == {
        "type": "Action.OpenUrl",
        "title": "Open",
        "url": "https://apps.apple.com/r/1",
    }
    assert len(second["items"]) == 2
    assert second["items"][1]["inlines"][0]["text"].endswith("x…")
    assert len(second["items"][1]["inlines"][0]["text"]) == 601


def test_caps_records_and_summarises_the_rest() -> None:
    hook = Hook()
    teams = sink(hook, max_records=2, max_rating=2)
    batch = [record(str(i), f"bad {i}", rating=10 if i == 0 else 1) for i in range(5)]
    result = teams.send(batch)
    assert (result.sent, result.skipped) == (2, 3)
    body = hook.card()["body"]
    assert len(body) == 4
    assert body[-1]["text"] == "…and 2 more matching feedback item(s)."


def test_nothing_selected_posts_nothing() -> None:
    hook = Hook()
    result = sink(hook, max_rating=2).send([record("1", "fine", rating=4)])
    assert (result.sent, result.skipped) == (0, 1)
    assert hook.requests == []


def test_errors_and_egress(monkeypatch: pytest.MonkeyPatch) -> None:
    result = sink(Hook(status=400)).send([record("1", "x")])
    assert result.errors == ["teams returned 400"]
    with pytest.raises(EgressError, match="blocked"):
        sink(Hook(), egress=EgressPolicy())
    monkeypatch.delenv("TEAMS_WEBHOOK_URL")
    with pytest.raises(SinkConfigError, match="TEAMS_WEBHOOK_URL"):
        sink(Hook())


def test_rating_outside_star_range_is_numeric() -> None:
    hook = Hook()
    sink(hook).send([record("1", "meh", rating=7)])
    head = hook.card()["body"][1]["items"][0]
    assert head["text"] == "appstore/us · rating 7"


def test_example_config_validates() -> None:
    config = load_config(EXAMPLE)
    registry = builtin_registry(config.plugins)
    assert registry.loaded_entry_points == ["teams"]
    assert config.egress is not None
    config.egress.check(URL)
    config.egress.check("https://default0123.ab.environment.api.powerplatform.com/powerautomate/x")
    for pipeline in config.pipelines:
        for source_spec in pipeline.sources:
            registry.source(source_spec.type).config_model.model_validate(source_spec.config)
        for spec in pipeline.enrichers:
            registry.enricher(spec.type).config_model.model_validate(spec.config)
        for spec in pipeline.sinks:
            registry.sink(spec.type).config_model.model_validate(spec.config)
