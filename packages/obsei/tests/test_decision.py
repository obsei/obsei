import json
from collections.abc import Callable, Iterator, Sequence
from datetime import UTC, datetime
from typing import Any, ClassVar

import httpx
import pytest
from pydantic import ValidationError

from obsei import Enrichment, Record, SourceRef
from obsei.ask import ask, judge_state
from obsei.config import ObseiConfig
from obsei.core.context import Context, LlmEndpoint
from obsei.core.protocols import Cursor, SinkResult
from obsei.enrichers import (
    Cascade,
    ClassifyPluginConfig,
    DecisionClassifier,
    DecisionFilter,
    FieldSpec,
    LlmClassifier,
    build_schema,
)
from obsei.enrichers.classify import build_classifier
from obsei.enrichers.filter import FilterConfig, build_filter
from obsei.llm import (
    ChoiceAnswer,
    ChoiceQuestion,
    DecisionClient,
    EgressError,
    EgressPolicy,
    LlmError,
    RequestBudget,
    ScoreAnswer,
    ScoreQuestion,
    YesNoAnswer,
    YesNoQuestion,
)
from obsei.llm.client import BudgetExceededError, ChatMessage, JsonSchema, LlmUnreachableError
from obsei.llm.decision import Question
from obsei.pipeline import Pipeline, SourceSpec, run
from obsei.sinks._common import label, matches
from obsei.store import Store

T0 = datetime(2026, 9, 1, tzinfo=UTC)
DECISION_URL = "http://decide.internal/decide"
Json = dict[str, Any]
Handler = Callable[[Json], Json]

ROUTE: Json = {
    "type": "choice",
    "choice": "billing",
    "probabilities": {"billing": 0.9049, "shipping": 0.0275, "technical": 0.0676},
    "confidence": 0.8574,
}
URGENCY: Json = {
    "type": "score",
    "score": 2.2821,
    "legend": {"0": "can wait", "1": "this week", "2": "today", "3": "right now"},
    "probabilities": {"0": 0.036, "1": 0.1937, "2": 0.2225, "3": 0.5478},
    "confidence": 0.2821,
}
QUESTIONS: dict[str, Question] = {
    "route": ChoiceQuestion(
        instructions="Which team should handle this?",
        criteria={
            "billing": "payments, charges, refunds",
            "shipping": "delivery",
            "technical": None,
        },
    ),
    "urgency": ScoreQuestion(
        instructions="How urgent is this?",
        criteria=["can wait", "this week", "today", "right now"],
    ),
    "angry": YesNoQuestion(instructions="Is the customer angry?"),
}


def rec(text: str, native_id: str = "1", rating: float | None = None) -> Record:
    return Record(
        source=SourceRef(type="zendesk", native_id=native_id),
        text=text,
        created_at=T0,
        rating=rating,
    )


class Server:
    """A decision endpoint (and optionally an OpenAI-compatible chat endpoint) behind
    ``httpx.MockTransport``; records every request."""

    def __init__(self, decide: Handler, chat: Json | None = None) -> None:
        self.decide = decide
        self.chat = chat
        self.requests: list[httpx.Request] = []

    def bodies(self, path: str | None = None) -> list[Json]:
        """Request bodies sent to ``path``, or to the decision endpoint."""
        return [
            json.loads(r.content)
            for r in self.requests
            if (r.url.path == path if path else r.url.path != "/v1/chat/completions")
        ]

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        body = json.loads(request.content)
        if request.url.path != "/v1/chat/completions":
            return httpx.Response(200, json=self.decide(body))
        if request.url.path == "/v1/chat/completions" and self.chat is not None:
            content = json.dumps(self.chat)
            return httpx.Response(200, json={"choices": [{"message": {"content": content}}]})
        return httpx.Response(404)

    @property
    def transport(self) -> httpx.MockTransport:
        return httpx.MockTransport(self)


def respond(answers: Json, model: str = "ggml-org/Julia-1-GGUF") -> Handler:
    def handler(body: Json) -> Json:
        return {"model": model, "answers": answers, "usage": {"input_tokens": 130}}

    return handler


def client(server: Server, url: str = DECISION_URL, **kw: Any) -> DecisionClient:
    return DecisionClient(url=url, policy=EgressPolicy(), transport=server.transport, **kw)


def test_decide_sends_the_documented_request_and_parses_answers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("JEV_KEY", "jev-test")
    server = Server(
        respond({"route": ROUTE, "urgency": URGENCY, "angry": {"type": "noul", "noul": 0.8208}})
    )
    answers = client(server, model="ggml-org/Kev-4B-GGUF", api_key_env="JEV_KEY").decide(
        "I was charged twice", QUESTIONS
    )

    (request,) = server.requests
    assert str(request.url) == DECISION_URL
    assert request.headers["authorization"] == "Bearer jev-test"
    assert request.extensions["obsei_egress"] is True
    assert json.loads(request.content) == {
        "model": "ggml-org/Kev-4B-GGUF",
        "state": "I was charged twice",
        "questions": {
            "route": {
                "type": "choice",
                "instructions": "Which team should handle this?",
                "criteria": {
                    "billing": "payments, charges, refunds",
                    "shipping": "delivery",
                    "technical": None,
                },
            },
            "urgency": {
                "type": "score",
                "instructions": "How urgent is this?",
                "criteria": ["can wait", "this week", "today", "right now"],
            },
            "angry": {"type": "noul", "instructions": "Is the customer angry?"},
        },
    }
    assert answers["route"].model_dump()["choice"] == "billing"
    urgency = answers["urgency"]
    assert isinstance(urgency, ScoreAnswer)
    assert urgency.label == "today"
    assert urgency.probabilities["right now"] == pytest.approx(0.5478)
    angry = answers["angry"]
    assert isinstance(angry, YesNoAnswer)
    assert angry.value is True
    assert angry.confidence == pytest.approx(0.8208)


def test_model_is_omitted_when_unset_and_learned_from_the_response() -> None:
    server = Server(respond({"angry": {"type": "noul", "noul": 0.1}}))
    decider = client(server)
    decider.decide("fine", {"angry": QUESTIONS["angry"]})
    assert "model" not in server.bodies()[0]
    assert decider.model == "ggml-org/Julia-1-GGUF"


@pytest.mark.parametrize(
    ("answers", "match"),
    [
        ({}, "'route' was not answered"),
        ({"route": {**ROUTE, "choice": "legal"}}, "not one of the options"),
        ({"route": {**ROUTE, "probabilities": {"legal": 1.0}}}, "unknown options"),
        ({"route": {"type": "noul", "noul": 0.5}}, "answered as noul"),
        ({"route": {**ROUTE, "confidence": 1.5}}, "invalid JSON"),
        ({"route": {k: v for k, v in ROUTE.items() if k != "probabilities"}}, "invalid JSON"),
    ],
)
def test_invalid_answers_are_rejected(answers: Json, match: str) -> None:
    server = Server(respond(answers))
    with pytest.raises(LlmError, match=match) as info:
        client(server).decide("x", {"route": QUESTIONS["route"]})
    assert DECISION_URL in str(info.value)


def test_score_outside_the_levels_is_rejected() -> None:
    server = Server(respond({"urgency": {**URGENCY, "score": 4.2}}))
    with pytest.raises(LlmError, match="outside 0-3"):
        client(server).decide("x", {"urgency": QUESTIONS["urgency"]})


def test_egress_budget_and_unreachable_endpoint() -> None:
    with pytest.raises(EgressError, match="air_gapped"):
        DecisionClient(url="https://api.jev.example.com/v1/decide", policy=EgressPolicy())

    def down(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused")

    unreachable = DecisionClient(
        url=DECISION_URL, policy=EgressPolicy(), transport=httpx.MockTransport(down)
    )
    with pytest.raises(LlmUnreachableError, match=f"decision model at {DECISION_URL}"):
        unreachable.decide("x", {"angry": QUESTIONS["angry"]})

    server = Server(respond({"angry": {"type": "noul", "noul": 0.1}}))
    capped = client(server, budget=RequestBudget(1))
    capped.decide("x", {"angry": QUESTIONS["angry"]})
    with pytest.raises(BudgetExceededError):
        capped.decide("x", {"angry": QUESTIONS["angry"]})


def test_every_hop_is_checked_against_the_policy() -> None:
    server = Server(respond({}))
    decider = client(server)
    request = httpx.Request("POST", "https://api.public.example.com/decide")
    request.extensions = {"obsei_egress": True}
    with pytest.raises(EgressError):
        decider._guard(request)


def test_endpoint_kinds() -> None:
    assert LlmEndpoint(base_url="http://localhost:11434/v1", model="qwen3:8b").api == "openai"
    with pytest.raises(ValidationError, match="needs a model"):
        LlmEndpoint(base_url="http://localhost:11434/v1")
    ctx = Context(
        llms={
            "julia": LlmEndpoint(api="decision", url=DECISION_URL),
            "chat": LlmEndpoint(base_url="http://localhost:11434/v1", model="qwen3:8b"),
        }
    )
    assert isinstance(ctx.decision("julia"), DecisionClient)
    with pytest.raises(KeyError, match="decision model, not a chat model"):
        ctx.chat("julia")
    with pytest.raises(KeyError, match="api: decision"):
        ctx.decision("chat")


def _ctx(server: Server, *, chat: bool = False) -> Context:
    llms = {"julia": LlmEndpoint(api="decision", url=DECISION_URL)}
    if chat:
        llms["ollama"] = LlmEndpoint(base_url="http://localhost:8080/v1", model="qwen3:8b")
    return Context(llms=llms, llm_transport=server.transport)


CLASSIFY: Json = {
    "llm": "julia",
    "intents": {"bug": "something is broken", "billing": "charges and refunds"},
    "fields": {
        "urgency": {
            "description": "How urgent is this?",
            "levels": ["can wait", "this week", "today", "right now"],
        },
        "competitor": {"description": "Does the customer mention a competitor?", "type": "yesno"},
    },
    "min_confidence": {"urgency": 0.25},
}


def _answers(intent_confidence: float = 0.9) -> Json:
    return {
        "sentiment": {
            "type": "choice",
            "choice": "negative",
            "probabilities": {"positive": 0.02, "negative": 0.9, "neutral": 0.05, "mixed": 0.03},
            "confidence": 0.88,
        },
        "intent": {
            "type": "choice",
            "choice": "billing",
            "probabilities": {"bug": 1 - intent_confidence, "billing": intent_confidence},
            "confidence": intent_confidence,
        },
        "urgency": URGENCY,
        "competitor": {"type": "noul", "noul": 0.1},
    }


def test_classify_asks_one_question_per_field_in_one_request() -> None:
    server = Server(respond(_answers()))
    classifier = build_classifier(ClassifyPluginConfig.model_validate(CLASSIFY), _ctx(server))
    assert isinstance(classifier, DecisionClassifier)
    record = rec("Charged twice!", rating=1).model_copy(update={"lang": "de"})
    (result,) = classifier.enrich([record])

    (body,) = server.bodies()
    assert body["state"] == "Message (source: zendesk, rating: 1):\n\nCharged twice!"
    assert list(body["questions"]) == ["sentiment", "intent", "urgency", "competitor"]
    assert body["questions"]["sentiment"]["criteria"]["positive"].startswith("satisfied")
    assert body["questions"]["intent"]["criteria"] == {
        "bug": "something is broken",
        "billing": "charges and refunds",
    }
    assert body["questions"]["urgency"]["type"] == "score"
    assert body["questions"]["competitor"] == {
        "type": "noul",
        "instructions": "Does the customer mention a competitor?",
    }

    assert result is not None
    assert result.model == "ggml-org/Julia-1-GGUF"
    assert result.confidence == pytest.approx(0.2821)
    value: Any = result.value
    assert value["sentiment"] == "negative"
    assert value["intent"] == "billing"
    assert value["language"] == "de"
    assert value["fields"] == {"urgency": "today", "competitor": False}
    assert value["scores"] == {"urgency": pytest.approx(2.2821)}
    assert value["probabilities"]["competitor"] == {"true": 0.1, "false": pytest.approx(0.9)}
    assert value["confidences"]["competitor"] == pytest.approx(0.9)
    assert value["review"] is False

    enriched = record.with_enrichment("classify", result)
    assert label(enriched, "classify.fields.urgency") == "today"
    assert label(enriched, "classify.fields.competitor") == "false"
    assert matches(
        enriched, {"classify.intent": ["billing"], "classify.fields.urgency": ["today"]}, None
    )


def test_below_the_cutoff_without_fallback_marks_for_review() -> None:
    server = Server(respond(_answers(intent_confidence=0.55)))
    classifier = build_classifier(ClassifyPluginConfig.model_validate(CLASSIFY), _ctx(server))
    (result,) = classifier.enrich([rec("hmm")])
    assert result is not None
    assert isinstance(result.value, dict)
    assert result.value["review"] is True
    assert result.value["uncertain"] == ["intent"]


def test_below_the_cutoff_falls_back_to_the_chat_model() -> None:
    chat = {
        "sentiment": "negative",
        "intent": "bug",
        "language": "en",
        "confidence": 0.9,
        "fields": {"urgency": "right now", "competitor": True},
    }
    server = Server(
        lambda body: respond(_answers(0.55 if "unsure" in body["state"] else 0.95))(body), chat
    )
    config = ClassifyPluginConfig.model_validate({**CLASSIFY, "fallback_llm": "ollama"})
    classifier = build_classifier(config, _ctx(server, chat=True))
    assert isinstance(classifier, Cascade)
    sure, unsure = classifier.enrich([rec("sure", "1"), rec("unsure", "2")])

    assert sure is not None
    assert unsure is not None
    assert sure.model == "ggml-org/Julia-1-GGUF"
    assert unsure.model == "qwen3:8b"
    assert isinstance(unsure.value, dict)
    assert unsure.value["fields"] == {"urgency": "right now", "competitor": True}
    (chat_body,) = server.bodies("/v1/chat/completions")
    schema = chat_body["response_format"]["json_schema"]["schema"]
    fields = schema["properties"]["fields"]["properties"]
    assert fields["competitor"]["anyOf"][0]["type"] == "boolean"
    assert fields["urgency"]["anyOf"][0]["enum"] == ["can wait", "this week", "today", "right now"]


def test_decision_classify_rejects_free_text_fields_and_unknown_cutoffs() -> None:
    server = Server(respond({}))
    free = ClassifyPluginConfig.model_validate(
        {"llm": "julia", "fields": {"summary": {"description": "One line summary"}}}
    )
    with pytest.raises(ValueError, match="choice, score and yesno"):
        build_classifier(free, _ctx(server))
    with pytest.raises(ValidationError, match="unknown fields"):
        ClassifyPluginConfig.model_validate({"min_confidence": {"nope": 0.5}})
    with pytest.raises(ValidationError, match="needs levels"):
        FieldSpec.model_validate({"description": "x", "type": "score"})


def test_existing_chat_config_still_works() -> None:
    config = ClassifyPluginConfig.model_validate(
        {
            "intents": ["bug", "other"],
            "fields": {"area": {"description": "Area", "choices": ["app", "web"]}},
        }
    )
    schema = build_schema(config)
    assert schema["properties"]["intent"]["enum"] == ["bug", "other"]  # type: ignore[index,call-overload]
    ctx = Context(llms={"default": LlmEndpoint(base_url="http://localhost:11434/v1", model="m")})
    assert isinstance(build_classifier(config, ctx), LlmClassifier)


class _Source:
    name: ClassVar[str] = "list"

    def __init__(self, texts: list[str]) -> None:
        self.texts = texts

    def fetch(self, cursor: Cursor | None) -> Iterator[tuple[Record, Cursor]]:
        for i, text in enumerate(self.texts):
            yield rec(text, str(i)), {"offset": i + 1}


class _Sink:
    name: ClassVar[str] = "memory"

    def __init__(self) -> None:
        self.received: list[Record] = []

    def send(self, batch: Sequence[Record]) -> SinkResult:
        self.received.extend(batch)
        return SinkResult(sent=len(batch))


class _Counter:
    name: ClassVar[str] = "count"
    version: ClassVar[str] = "1"

    def __init__(self) -> None:
        self.seen: list[str] = []

    def enrich(self, batch: Sequence[Record]) -> list[Enrichment | None]:
        self.seen.extend(r.text for r in batch)
        return [Enrichment(value=1) for _ in batch]


def _spam(body: Json) -> Json:
    p = 0.97 if "WIN" in body["state"] else 0.04
    return respond({"match": {"type": "noul", "noul": p}})(body)


@pytest.mark.parametrize("action", ["drop", "tag"])
def test_filter_drops_or_tags_matching_records(action: str) -> None:
    server = Server(_spam)
    spam_filter = build_filter(
        FilterConfig.model_validate(
            {"llm": "julia", "question": "Is this spam?", "threshold": 0.8, "action": action}
        ),
        _ctx(server),
    )
    assert isinstance(spam_filter, DecisionFilter)
    counter, sink = _Counter(), _Sink()
    store = Store(allow_unencrypted=True)
    report = run(
        Pipeline(
            name="p",
            sources=[SourceSpec("s", _Source(["App crashes on login", "WIN a FREE phone"]))],
            enrichers=[spam_filter, counter],
            sinks=[sink],
            allow_unredacted=True,
        ),
        store,
    )
    body = server.bodies()[0]
    assert body["questions"] == {"match": {"type": "noul", "instructions": "Is this spam?"}}
    if action == "drop":
        assert report.dropped == {"filter": 1}
        assert counter.seen == ["App crashes on login"]
        assert [r.text for r in sink.received] == ["App crashes on login"]
        assert store.count() == 1
    else:
        assert report.dropped == {}
        assert store.count() == 2
        spam = next(r for r in sink.received if r.text.startswith("WIN"))
        assert label(spam, "filter.match") == "true"
        assert spam.enrichments["filter"].confidence == pytest.approx(0.97)
    assert store.retry_records("p", "s", 10) == []


def test_filter_needs_a_decision_endpoint() -> None:
    ctx = Context(llms={"default": LlmEndpoint(base_url="http://localhost:11434/v1", model="m")})
    with pytest.raises(KeyError, match="api: decision"):
        build_filter(FilterConfig(question="Is this spam?"), ctx)


class _Chat:
    model = "fake"

    def __init__(self, reply: Json) -> None:
        self.reply = reply

    def complete(self, messages: Sequence[ChatMessage], *, schema: JsonSchema) -> str:
        return json.dumps(self.reply)


@pytest.fixture
def feedback_store() -> Store:
    store = Store(allow_unencrypted=True)
    store.upsert([rec("I cannot log in, email <EMAIL>", "1"), rec("Refund my double charge", "2")])
    return store


@pytest.mark.parametrize(("p", "unsupported"), [(0.93, False), (0.2, True)])
def test_ask_judge_scores_grounding_on_cited_redacted_records(
    feedback_store: Store, p: float, unsupported: bool
) -> None:
    login = rec("x", "1").id
    server = Server(respond({"grounded": {"type": "noul", "noul": p}}))
    chat = _Chat({"answer": f"Login fails [{login}]", "citations": [login]})
    answer = ask(
        feedback_store, "log in problems?", chat, judge=client(server), judge_threshold=0.5
    )

    assert answer.grounded == pytest.approx(p)
    assert answer.unsupported is unsupported
    (body,) = server.bodies()
    assert body["questions"] == {
        "grounded": {
            "type": "noul",
            "instructions": "Is every statement in the answer supported by the quoted records?",
        }
    }
    assert f"[{login}] (zendesk, 2026-09-01): I cannot log in, email <EMAIL>" in body["state"]
    assert "Refund" not in body["state"]
    assert body["state"].endswith(f"Answer:\nLogin fails [{login}]")


def test_ask_keeps_the_answer_when_the_judge_fails(feedback_store: Store) -> None:
    server = Server(respond({}))
    chat = _Chat({"answer": "Nothing found", "citations": []})
    answer = ask(feedback_store, "anything?", chat, judge=client(server))
    assert answer.text == "Nothing found"
    assert answer.grounded is None
    assert answer.judge_error is not None
    assert "was not answered" in answer.judge_error
    assert "(none)" in judge_state("q", "a", [])


def test_ask_judge_must_be_a_decision_endpoint() -> None:
    base: Json = {
        "llms": {"chat": {"base_url": "http://localhost:11434/v1", "model": "m"}},
        "ask_llm": "chat",
        "pipelines": [{"name": "p", "sources": [{"key": "c", "type": "csv"}]}],
    }
    with pytest.raises(ValidationError, match="api: decision"):
        ObseiConfig.model_validate({**base, "ask_judge": "chat"})
    config = ObseiConfig.model_validate(
        {
            **base,
            "llms": {
                **base["llms"],
                "judge": {"api": "decision", "url": "http://judge.internal/decide"},
            },
            "ask_judge": "judge",
        }
    )
    assert config.ask_judge_threshold == 0.5


def test_slack_and_api_text_flag_unsupported_answers() -> None:
    pytest.importorskip("mcp")
    from obsei.ask import Answer  # noqa: PLC0415
    from obsei.serve import Handlers  # noqa: PLC0415

    grounded = Answer(text="Login fails", citations=["rec_1"], evidence=[], grounded=0.93)
    assert Handlers.render(grounded).endswith("_grounded: 0.93_")
    shaky = Answer(
        text="Everyone hates it", citations=[], evidence=[], grounded=0.2, unsupported=True
    )
    assert "possibly unsupported by the cited feedback (grounded 0.20)" in Handlers.render(shaky)


@pytest.mark.parametrize(
    ("status", "match"),
    [
        (400, "rejected the request: too many options"),
        (501, "http://decide.internal/decide is not serving a decision model"),
        (503, "decision request to http://decide.internal/decide failed"),
    ],
)
def test_server_errors_name_the_endpoint(status: int, match: str) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status, text="too many options")

    decider = DecisionClient(
        url=DECISION_URL,
        policy=EgressPolicy(),
        transport=httpx.MockTransport(handler),
    )
    with pytest.raises(LlmError, match=match):
        decider.decide("x", {"angry": QUESTIONS["angry"]})


def test_state_objects_and_yes_no_criteria_are_sent_as_json() -> None:
    server = Server(respond({"angry": {"type": "noul", "noul": 0.3}}))
    question = YesNoQuestion(
        instructions="Is the customer angry?",
        criteria={"true": "insults, threats, all caps", "false": "calm, even if unhappy"},
    )
    client(server).decide({"ticket": "Where is my parcel?", "priority": "low"}, {"angry": question})
    body = server.bodies()[0]
    assert body["state"] == {"ticket": "Where is my parcel?", "priority": "low"}
    assert body["questions"]["angry"]["criteria"] == {
        "true": "insults, threats, all caps",
        "false": "calm, even if unhappy",
    }


CLEF = "https://api.cloudflare.com/client/v4/accounts/acc123/ai/run/@cf/cloudflare/clef"


@pytest.mark.parametrize("wrapped", [True, False])
def test_workers_ai_url_is_used_as_is_and_its_envelope_unwrapped(
    monkeypatch: pytest.MonkeyPatch, wrapped: bool
) -> None:
    monkeypatch.setenv("CF_TOKEN", "cf-test")
    inner = {"answers": {"route": ROUTE}, "usage": {"input_tokens": 90, "output_tokens": 0}}
    server = Server(
        lambda body: {"result": inner, "success": True, "errors": []} if wrapped else inner
    )
    policy = EgressPolicy(mode="private", allowed_hosts=frozenset({"api.cloudflare.com"}))
    decider = DecisionClient(
        url=CLEF,
        policy=policy,
        model="clef",
        api_key_env="CF_TOKEN",
        transport=server.transport,
    )
    answers = decider.decide("refund please", {"route": QUESTIONS["route"]})
    (request,) = server.requests
    assert str(request.url) == CLEF
    assert request.headers["authorization"] == "Bearer cf-test"
    assert json.loads(request.content)["model"] == "clef"
    assert isinstance(answers["route"], ChoiceAnswer)
    assert answers["route"].choice == "billing"
    assert decider.model == "clef"


def test_workers_ai_failure_and_egress() -> None:
    with pytest.raises(EgressError):
        DecisionClient(url=CLEF, policy=EgressPolicy())
    server = Server(lambda body: {"result": None, "success": False, "errors": [{"code": 5006}]})
    decider = DecisionClient(
        url=CLEF, policy=EgressPolicy(mode="hybrid"), transport=server.transport
    )
    with pytest.raises(LlmError, match="5006"):
        decider.decide("x", {"route": QUESTIONS["route"]})


def test_yes_no_with_descriptions_is_asked_as_a_two_option_choice() -> None:
    def spam_choice(body: Json) -> Json:
        p = 0.99 if "WIN" in body["state"] else 0.02
        answer = {
            "type": "choice",
            "choice": "yes" if p > 0.5 else "no",
            "probabilities": {"yes": p, "no": 1 - p},
            "confidence": 0.9,
        }
        return respond({"match": answer})(body)

    server = Server(spam_choice)
    config = FilterConfig.model_validate(
        {
            "llm": "julia",
            "question": "Is this a real customer request or spam?",
            "yes_means": "prize scams, phishing links, advertising",
            "no_means": "a customer writing about a product, an account or a bill",
            "threshold": 0.8,
        }
    )
    tagged = build_filter(config, _ctx(server)).enrich([rec("WIN a phone"), rec("Refund me")])
    assert server.bodies()[0]["questions"]["match"] == {
        "type": "choice",
        "instructions": "Is this a real customer request or spam?",
        "criteria": {
            "yes": "prize scams, phishing links, advertising",
            "no": "a customer writing about a product, an account or a bill",
        },
    }
    assert [e.value["match"] for e in tagged if e and isinstance(e.value, dict)] == [True, False]
    with pytest.raises(ValidationError, match="go together"):
        FilterConfig.model_validate({"question": "Spam?", "yes_means": "spam"})

    field = FieldSpec.model_validate(
        {
            "description": "Refund?",
            "type": "yesno",
            "yes_means": "asks for money back",
            "no_means": "does not",
        }
    )
    server = Server(
        respond(
            {
                **_answers(),
                "competitor": {
                    "type": "choice",
                    "choice": "yes",
                    "probabilities": {"yes": 0.8, "no": 0.2},
                    "confidence": 0.6,
                },
            }
        )
    )
    config_classify = ClassifyPluginConfig.model_validate(
        {**CLASSIFY, "fields": {**CLASSIFY["fields"], "competitor": field.model_dump()}}
    )
    (result,) = build_classifier(config_classify, _ctx(server)).enrich([rec("x")])
    assert result is not None
    value: Any = result.value
    assert value["fields"]["competitor"] is True
    assert value["confidences"]["competitor"] == pytest.approx(0.8)


def test_decision_endpoints_take_the_full_url() -> None:
    endpoint = LlmEndpoint(api="decision", url=DECISION_URL)
    assert endpoint.address == DECISION_URL
    for bad in (
        {"api": "decision", "base_url": "http://localhost:8080"},
        {"api": "decision"},
        {"api": "decision", "url": DECISION_URL, "url_env": "X"},
        {"api": "decision", "url": "http://localhost:8080"},
        {"api": "decision", "url": "ftp://localhost/decide"},
    ):
        with pytest.raises(ValidationError, match=r"set url \(or url_env\)"):
            LlmEndpoint.model_validate(bad)
    with pytest.raises(ValidationError, match="takes base_url, not url"):
        LlmEndpoint(url=DECISION_URL, model="m")
    with pytest.raises(LlmError, match="full decision endpoint URL"):
        DecisionClient(url="http://localhost:8080/", policy=EgressPolicy())


def test_decision_url_from_the_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    endpoint = LlmEndpoint(api="decision", url_env="TEST_DECISION_URL")
    ctx = Context(llms={"julia": endpoint})
    monkeypatch.delenv("TEST_DECISION_URL", raising=False)
    with pytest.raises(LlmError, match="TEST_DECISION_URL is not set") as info:
        ctx.decision("julia")
    assert "/v1/" in str(info.value)
    monkeypatch.setenv("TEST_DECISION_URL", "http://localhost:8080")
    with pytest.raises(LlmError, match=r"TEST_DECISION_URL: .* not a decision endpoint URL"):
        ctx.decision("julia")
    monkeypatch.setenv("TEST_DECISION_URL", DECISION_URL)
    assert ctx.decision("julia").url == DECISION_URL
    assert endpoint.address == "$TEST_DECISION_URL"
