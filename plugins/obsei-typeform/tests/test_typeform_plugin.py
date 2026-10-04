from pathlib import Path

import httpx
import pytest
from pydantic import JsonValue

from obsei.config import builtin_registry, load_config
from obsei.core.context import Context
from obsei.core.protocols import Cursor, Source
from obsei.core.registry import Registry
from obsei_typeform import TypeformError, register

EXAMPLE = Path(__file__).parents[3] / "examples" / "surveys-typeform.yaml"


def response(token: str, submitted: str, text: str | None = "Setup was confusing") -> JsonValue:
    answers: list[JsonValue] = [
        {"field": {"id": "f1", "ref": "nps", "type": "nps"}, "type": "number", "number": 3},
        {
            "field": {"id": "f2", "ref": "email", "type": "email"},
            "type": "email",
            "email": "jane@example.com",
        },
        {
            "field": {"id": "f3", "ref": "plan", "type": "multiple_choice"},
            "type": "choice",
            "choice": {"label": "Team"},
        },
        {
            "field": {"id": "f4", "ref": "liked", "type": "multiple_choice"},
            "type": "choices",
            "choices": {"labels": ["Speed", "Price"], "other": "Docs"},
        },
    ]
    if text is not None:
        answers.append(
            {
                "field": {"id": "f5", "ref": "better", "type": "long_text"},
                "type": "text",
                "text": text,
            }
        )
    return {
        "response_id": token,
        "token": token,
        "landed_at": submitted,
        "submitted_at": submitted,
        "metadata": {"platform": "mobile", "referer": "https://example.com/?email=jane"},
        "hidden": {"lang": "de", "uid": "user-42", "email": "jane@example.com"},
        "answers": answers,
    }


class Api:
    def __init__(self, pages: list[list[JsonValue]]) -> None:
        self.pages = pages
        self.requests: list[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        items = self.pages.pop(0) if self.pages else []
        return httpx.Response(200, json={"total_items": len(items), "items": items})


def source(api: Api, salt: bytes | None = None, **config: JsonValue) -> Source:
    registry = Registry()
    register(registry)
    ctx = Context(http=httpx.Client(transport=httpx.MockTransport(api)), salt=salt)
    return registry.source("typeform").create({"form_id": "aBcD1234", **config}, ctx)


@pytest.fixture(autouse=True)
def token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TYPEFORM_TOKEN", "tfp_secret")


def test_maps_text_answers_only_by_default() -> None:
    api = Api([[response("r1", "2026-09-01T10:00:00Z")]])
    ((record, cursor),) = list(source(api, rating_field="nps").fetch(None))
    assert record.text == "Setup was confusing"
    assert record.rating == 3
    assert record.source.type == "typeform"
    assert record.source.instance == "aBcD1234"
    assert record.source.native_id == "r1"
    assert record.author is None
    assert record.lang is None
    assert record.context == {"form": "aBcD1234", "platform": "mobile"}
    assert "jane" not in record.model_dump_json()
    assert cursor == {"since": "2026-09-01T10:00:00+00:00"}
    request = api.requests[0]
    assert request.url.path == "/forms/aBcD1234/responses"
    assert request.headers["Authorization"] == "Bearer tfp_secret"
    assert request.url.params["completed"] == "true"
    assert "since" not in request.url.params


def test_text_fields_hidden_lang_and_author() -> None:
    api = Api([[response("r1", "2026-09-01T10:00:00Z")]])
    configured = source(
        api,
        salt=b"0123456789abcdef",
        text_fields=["better", "f3", "liked"],
        lang_hidden_field="lang",
        author_hidden_field="uid",
        instance="onboarding",
        api_base="https://api.eu.typeform.com",
    )
    ((record, _),) = list(configured.fetch(None))
    assert record.text == "Setup was confusing\n\nTeam\n\nSpeed, Price, Docs"
    assert record.lang == "de"
    assert record.author is not None
    assert record.author.locale == "de"
    assert record.rating is None
    assert record.source.instance == "onboarding"
    assert api.requests[0].url.host == "api.eu.typeform.com"


def test_pages_back_with_before_and_moves_cursor_last() -> None:
    api = Api(
        [
            [response("r3", "2026-09-03T00:00:00Z"), response("r2", "2026-09-02T00:00:00Z")],
            [response("r1", "2026-09-01T00:00:00Z")],
        ]
    )
    cursor: Cursor = {"since": "2026-08-01T00:00:00+00:00"}
    fetched = list(source(api, page_size=2).fetch(cursor))
    assert [r.source.native_id for r, _ in fetched] == ["r3", "r2", "r1"]
    assert fetched[0][1] == {
        "since": "2026-08-01T00:00:00+00:00",
        "before": "r3",
        "newest": "2026-09-03T00:00:00+00:00",
    }
    assert fetched[-1][1] == {"since": "2026-09-03T00:00:00+00:00"}
    first, second = api.requests
    assert first.url.params["since"] == "2026-07-31T23:59:59"
    assert "before" not in first.url.params
    assert second.url.params["before"] == "r2"
    assert first.url.params["page_size"] == "2"


def test_max_pages_resumes_from_before_token() -> None:
    api = Api([[response("r3", "2026-09-03T00:00:00Z"), response("r2", "2026-09-02T00:00:00Z")]])
    ((_, _), (_, cursor)) = list(source(api, page_size=2, max_pages=1).fetch(None))
    assert cursor == {"since": None, "before": "r2", "newest": "2026-09-03T00:00:00+00:00"}

    api = Api([[response("r1", "2026-09-01T00:00:00Z")]])
    ((record, final),) = list(source(api, page_size=2).fetch(cursor))
    assert record.source.native_id == "r1"
    assert api.requests[0].url.params["before"] == "r2"
    assert final == {"since": "2026-09-03T00:00:00+00:00"}


def test_finished_backlog_restarts_from_newest() -> None:
    api = Api([[], [response("r4", "2026-09-04T00:00:00Z")]])
    cursor: Cursor = {"since": None, "before": "r1", "newest": "2026-09-03T00:00:00+00:00"}
    ((record, final),) = list(source(api).fetch(cursor))
    assert record.source.native_id == "r4"
    assert final == {"since": "2026-09-04T00:00:00+00:00"}
    resumed, fresh = api.requests
    assert resumed.url.params["before"] == "r1"
    assert "before" not in fresh.url.params
    assert fresh.url.params["since"] == "2026-09-02T23:59:59"


def test_skips_responses_without_text() -> None:
    api = Api(
        [[response("r2", "2026-09-02T00:00:00Z", None), response("r1", "2026-09-01T00:00:00Z")]]
    )
    ((record, cursor),) = list(source(api).fetch(None))
    assert record.source.native_id == "r1"
    assert cursor == {"since": "2026-09-02T00:00:00+00:00"}


def test_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    def denied(_: httpx.Request) -> httpx.Response:
        return httpx.Response(403)

    registry = Registry()
    register(registry)
    ctx = Context(http=httpx.Client(transport=httpx.MockTransport(denied)))
    failing = registry.source("typeform").create({"form_id": "aBcD1234"}, ctx)
    with pytest.raises(TypeformError, match="403"):
        list(failing.fetch(None))
    monkeypatch.delenv("TYPEFORM_TOKEN")
    with pytest.raises(TypeformError, match="TYPEFORM_TOKEN"):
        list(failing.fetch(None))
    with pytest.raises(ValueError, match="form_id"):
        registry.source("typeform").create({"form_id": "../x"}, ctx)


def test_example_config_validates() -> None:
    config = load_config(EXAMPLE)
    registry = builtin_registry(config.plugins)
    assert registry.loaded_entry_points == ["typeform"]
    for pipeline in config.pipelines:
        for source_spec in pipeline.sources:
            registry.source(source_spec.type).config_model.model_validate(source_spec.config)
        for spec in pipeline.enrichers:
            registry.enricher(spec.type).config_model.model_validate(spec.config)
        for spec in pipeline.sinks:
            registry.sink(spec.type).config_model.model_validate(spec.config)
