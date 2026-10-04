import json
from collections.abc import Iterator, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, ClassVar

import duckdb
import httpx
import pytest
from pydantic import BaseModel, JsonValue, ValidationError

from obsei import Enrichment, Record, SourceRef
from obsei.config import ConfigError, ObseiConfig, build_pipeline, load_config
from obsei.core.context import Context, LlmEndpoint
from obsei.core.protocols import Cursor, SinkResult
from obsei.llm import EgressPolicy
from obsei.pipeline import Pipeline, PipelineError, SourceSpec, run
from obsei.routing import ROUTE, Route, Router, When
from obsei.sinks._common import matches
from obsei.sinks.slack import SlackConfig
from obsei.store import Query, Store
from obsei.studio import overview

T0 = datetime(2026, 9, 1, tzinfo=UTC)
LEVELS = ["can wait", "this week", "today", "right now"]
DECISION_URL = "http://decide.internal/decide"
Json = dict[str, Any]


def decided(
    intent: str = "bug",
    *,
    confidence: float = 0.9,
    urgency: str = "today",
    score: float = 2.2,
    refund: float = 0.1,
    review: bool = False,
) -> Enrichment:
    return Enrichment(
        value={
            "sentiment": "negative",
            "intent": intent,
            "fields": {"urgency": urgency, "refund": refund >= 0.5},
            "probabilities": {
                "intent": {intent: confidence, "other": 1 - confidence},
                "refund": {"true": refund, "false": 1 - refund},
            },
            "scores": {"urgency": score},
            "confidences": {
                "intent": confidence,
                "urgency": 0.4,
                "refund": max(refund, 1 - refund),
            },
            "levels": {"urgency": LEVELS},
            "review": review,
        },
        confidence=min(confidence, 0.4),
    )


def chatted(intent: str = "bug", urgency: str = "today", confidence: float = 0.8) -> Enrichment:
    return Enrichment(
        value={"sentiment": "negative", "intent": intent, "fields": {"urgency": urgency}},
        confidence=confidence,
    )


def rec(
    enrichment: Enrichment | None = None, *, rating: float | None = 1, native_id: str = "1"
) -> Record:
    record = Record(
        source=SourceRef(type="zendesk", native_id=native_id),
        text="Checkout fails",
        created_at=T0,
        rating=rating,
    )
    return record.with_enrichment("classify", enrichment) if enrichment else record


def when(raw: dict[str, object], **kwargs: Any) -> When:
    return When.parse(raw, **kwargs)


def test_lists_of_values_match_as_before() -> None:
    record = rec(decided())
    assert matches(record, {"classify.intent": ["bug", "billing"]}, None)
    assert not matches(record, {"classify.intent": ["billing"]}, None)
    assert matches(record, {"classify.fields.refund": ["false"]}, None)
    assert not matches(record, {"classify.intent": ["bug"]}, 0.5)
    assert not matches(rec(), {"classify.intent": ["bug"]}, None)
    assert matches(rec(), {}, None)


def test_is_with_min_confidence_uses_the_answer_confidence() -> None:
    rule = when({"classify.intent": {"is": ["bug", "question"], "min_confidence": 0.8}})
    assert rule.matches(rec(decided(confidence=0.9)))
    assert not rule.matches(rec(decided(confidence=0.6)))
    assert not rule.matches(rec(decided("billing", confidence=0.9)))
    assert rule.matches(rec(chatted(confidence=0.85)))
    assert not rule.matches(rec(chatted(confidence=0.7)))
    assert when({"classify.intent": {"is": "bug"}}).matches(rec(chatted()))


def test_score_bounds_compare_by_level_order_or_expected_score() -> None:
    at_least_today = when({"classify.fields.urgency": {"gte": "today"}})
    assert at_least_today.matches(rec(decided(urgency="today")))
    assert at_least_today.matches(rec(decided(urgency="right now")))
    assert not at_least_today.matches(rec(decided(urgency="this week")))
    assert when({"classify.fields.urgency": {"lte": "this week"}}).matches(
        rec(decided(urgency="can wait"))
    )
    assert when({"classify.fields.urgency": {"gte": 2.0, "lte": 2.5}}).matches(
        rec(decided(score=2.2))
    )
    assert not when({"classify.fields.urgency": {"gte": 2.5}}).matches(rec(decided(score=2.2)))
    # chat results store no levels: the pipeline's classify levels order them
    assert not at_least_today.matches(rec(chatted(urgency="right now")))
    configured = when(
        {"classify.fields.urgency": {"gte": "today"}},
        levels={"classify.fields.urgency": LEVELS},
    )
    assert configured.matches(rec(chatted(urgency="right now")))
    assert not configured.matches(rec(chatted(urgency="can wait")))
    assert when(
        {"classify.fields.urgency": {"gte": 3}}, levels={"classify.fields.urgency": LEVELS}
    ).matches(rec(chatted(urgency="right now")))


def test_yes_no_fields_match_by_value_or_probability() -> None:
    assert when({"classify.fields.refund": {"is": True}}).matches(rec(decided(refund=0.8)))
    assert not when({"classify.fields.refund": {"is": True}}).matches(rec(decided(refund=0.2)))
    likely = when({"classify.fields.refund": {"min_probability": 0.7}})
    assert likely.matches(rec(decided(refund=0.75)))
    assert not likely.matches(rec(decided(refund=0.6)))
    assert when({"classify.fields.refund": {"is": False, "min_probability": 0.7}}).matches(
        rec(decided(refund=0.2))
    )
    assert when({"classify.intent": {"min_probability": 0.85, "is": "bug"}}).matches(
        rec(decided(confidence=0.9))
    )
    spam = rec().with_enrichment(
        "filter",
        Enrichment(value={"match": True, "probability": 0.92, "action": "tag"}, confidence=0.92),
    )
    assert when({"filter.match": {"min_probability": 0.9}}).matches(spam)
    assert not when({"filter.match": {"min_probability": 0.95}}).matches(spam)


def test_review_and_max_rating() -> None:
    flagged, clear = rec(decided(review=True)), rec(decided())
    assert when({"review": True}).matches(flagged)
    assert not when({"review": True}).matches(clear)
    assert when({"review": False}).matches(clear)
    assert when({"max_rating": 2}).matches(clear)
    assert not when({"max_rating": 2}).matches(rec(decided(), rating=4))
    assert not when({"max_rating": 2}).matches(rec(decided(), rating=None))
    assert not when({"max_rating": 3}, max_rating=0.5).matches(clear)


@pytest.mark.parametrize(
    ("raw", "message"),
    [
        ({"classify.intent": {"is": []}}, "classify.intent: is"),
        ({"classify.intent": {"min_confidence": 2}}, "min_confidence"),
        ({"classify.intent": {"bogus": 1}}, "bogus"),
        ({"classify.intent": {}}, "at least one"),
        ({"classify.intent": 3}, "list of values"),
        ({"review": "yes"}, "review: expected true or false"),
        ({"max_rating": "low"}, "max_rating: expected a number"),
        ({"classify..intent": ["bug"]}, "not a dotted path"),
    ],
)
def test_bad_conditions_are_rejected(raw: dict[str, object], message: str) -> None:
    with pytest.raises(ValueError, match=message):
        When.parse(raw)


def test_sink_configs_validate_conditions() -> None:
    config = SlackConfig.model_validate(
        {"when": {"classify.intent": {"is": "bug", "min_confidence": 0.8}, "review": False}}
    )
    assert isinstance(config.when["classify.intent"], dict)
    with pytest.raises(ValidationError, match="min_confidence"):
        SlackConfig.model_validate({"when": {"classify.intent": {"min_confidence": 7}}})


class Memory:
    name: ClassVar[str] = "memory"

    def __init__(self) -> None:
        self.received: list[str] = []

    def send(self, batch: Sequence[Record]) -> SinkResult:
        self.received.extend(r.id for r in batch)
        return SinkResult(sent=len(batch))


class Fixed:
    name: ClassVar[str] = "fixed"

    def __init__(self, records: list[Record]) -> None:
        self.records = records

    def fetch(self, cursor: Cursor | None) -> Iterator[tuple[Record, Cursor]]:
        for i, record in enumerate(self.records):
            yield record, {"offset": i + 1}


def test_first_matching_route_wins_and_unrouted_sinks_get_everything() -> None:
    bug = rec(decided("bug", urgency="right now"), native_id="1")
    slow = rec(decided("bug", urgency="can wait"), native_id="2")
    billing = rec(decided("billing", urgency="can wait"), native_id="3")
    unsure = rec(decided("bug", urgency="right now", review=True), native_id="4")
    router = Router(
        (
            Route("review", ("triage",), When(review=True)),
            Route(
                "urgent", ("jira", "oncall"), when({"classify.fields.urgency": {"gte": "today"}})
            ),
            Route("billing", ("billing",), when({"classify.intent": ["billing"]})),
            Route("default", ("lake",)),
        )
    )
    sinks = {k: Memory() for k in ("triage", "jira", "oncall", "billing", "lake", "audit")}
    store = Store(allow_unencrypted=True)
    report = run(
        Pipeline(
            name="p",
            sources=[SourceSpec("s", Fixed([bug, slow, billing, unsure]))],
            sinks=list(sinks.values()),
            sink_keys=list(sinks),
            router=router,
            allow_unredacted=True,
        ),
        store,
    )
    assert sinks["triage"].received == [unsure.id]
    assert sinks["jira"].received == sinks["oncall"].received == [bug.id]
    assert sinks["billing"].received == [billing.id]
    assert sinks["lake"].received == [slow.id]
    assert sinks["audit"].received == [bug.id, slow.id, billing.id, unsure.id]
    assert report.sent == {"triage": 1, "jira": 1, "oncall": 1, "billing": 1, "lake": 1, "audit": 4}
    stored = store.get(bug.id)
    assert stored is not None
    assert stored.enrichments[ROUTE].value == {"rule": "urgent", "sinks": ["jira", "oncall"]}
    counts = {r.key: r.count for r in store.stats(Query(), "route")}
    assert counts == {"review": 1, "urgent": 1, "billing": 1, "default": 1}
    assert {b.key for b in overview(store, k=1).by_route} == set(counts)
    assert overview(store, k=2).by_route == []


def test_records_no_route_matches_are_marked_unrouted() -> None:
    router = Router((Route("bugs", ("jira",), when({"classify.intent": ["bug"]})),))
    routed = router.apply(rec(decided("billing")))
    assert routed.enrichments[ROUTE].value == {"rule": "unrouted", "sinks": []}


def test_pipelines_reject_routes_to_unknown_or_ambiguous_sinks() -> None:
    source = [SourceSpec("s", Fixed([]))]
    router = Router((Route("default", ("lake",)),))
    with pytest.raises(PipelineError, match="unknown sinks"):
        Pipeline(name="p", sources=source, sinks=[Memory()], router=router, allow_unredacted=True)
    with pytest.raises(PipelineError, match="unique"):
        Pipeline(
            name="p",
            sources=source,
            sinks=[Memory(), Memory()],
            sink_keys=["lake", "lake"],
            router=router,
            allow_unredacted=True,
        )
    with pytest.raises(PipelineError, match="name every sink"):
        Pipeline(
            name="p", sources=source, sinks=[Memory()], sink_keys=["a", "b"], allow_unredacted=True
        )


CLASSIFY: Json = {
    "type": "classify",
    "config": {
        "llm": "julia",
        "intents": ["bug", "billing", "other"],
        "fields": {
            "urgency": {"description": "How urgent?", "levels": LEVELS},
            "refund": {"description": "Asks for money back?", "type": "yesno"},
        },
    },
}


def pipeline_config(**overrides: JsonValue) -> Json:
    base: Json = {
        "name": "tickets",
        "sources": [{"key": "csv", "type": "csv", "config": {"path": "x.csv"}}],
        "enrichers": [CLASSIFY],
        "sinks": [
            {
                "key": "jira",
                "type": "jira",
                "config": {"base_url": "https://acme.atlassian.net", "project_key": "SUP"},
            },
            {"key": "oncall", "type": "slack", "config": {"webhook_url_env": "ONCALL_URL"}},
            {"key": "lake", "type": "parquet", "config": {"directory": "lake"}},
        ],
    }
    return {**base, **overrides}


def load(pipeline: Json) -> ObseiConfig:
    return ObseiConfig.model_validate({"version": 1, "pipelines": [pipeline]})


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        (
            {"route": [{"when": {"classify.intent": ["bug"]}, "sinks": ["nope"]}]},
            r"route 1: no sink with key \['nope'\]",
        ),
        (
            {"route": [{"default": ["lake"]}, {"review": ["oncall"]}]},
            "route 1: default must be the last",
        ),
        ({"route": [{"when": {"classify.intent": ["bug"]}}]}, "when and sinks go together"),
        ({"route": [{"review": ["lake"], "default": ["lake"]}]}, "exactly one of"),
        (
            {"route": [{"name": "x", "review": ["lake"]}, {"name": "x", "default": ["lake"]}]},
            r"route 2 \(x\): route names must be unique",
        ),
        (
            {
                "route": [
                    {
                        "name": "urgent",
                        "when": {"classify.fields.urgency": {"gte": "soon"}},
                        "sinks": ["jira"],
                    }
                ]
            },
            r"route 1 \(urgent\): when.classify.fields.urgency: 'soon' is not one of the levels",
        ),
        (
            {"route": [{"when": {"classify.intent": {"gte": "bug"}}, "sinks": ["jira"]}]},
            "needs a score field",
        ),
        (
            {
                "route": [
                    {
                        "when": {"classify.intent": {"is": "bug", "min_confidence": 9}},
                        "sinks": ["jira"],
                    }
                ]
            },
            "route 1: when.classify.intent: min_confidence",
        ),
        (
            {
                "sinks": [
                    {
                        "type": "slack",
                        "config": {"when": {"classify.fields.urgency": {"lte": "later"}}},
                    }
                ]
            },
            "sink 'slack': when.classify.fields.urgency: 'later' is not one of the levels",
        ),
        (
            {"sinks": [{"type": "slack", "config": {"when": {"classify.intent": {"is": []}}}}]},
            "sink 'slack': when.classify.intent",
        ),
        (
            {
                "sinks": [
                    {"type": "parquet", "config": {"directory": "a"}},
                    {"type": "parquet", "config": {"directory": "b"}},
                ],
                "route": [{"default": ["parquet"]}],
            },
            "sink keys must be unique",
        ),
        (
            {
                "sinks": [
                    {"key": "parquet", "type": "parquet", "config": {"directory": "a"}},
                    {"type": "parquet", "config": {"directory": "b"}},
                ]
            },
            "sink keys must be unique",
        ),
    ],
)
def test_config_errors_name_the_route_or_sink(overrides: Json, message: str) -> None:
    with pytest.raises(ValidationError, match=message):
        load(pipeline_config(**overrides))


def test_unkeyed_sinks_of_one_type_still_load_without_routes() -> None:
    config = load(
        pipeline_config(
            sinks=[
                {"type": "slack", "config": {"when": {"classify.intent": ["bug"]}}},
                {"type": "slack", "config": {"when": {"classify.intent": ["billing"]}}},
            ]
        )
    )
    assert [s.name for s in config.pipelines[0].sinks] == ["slack", "slack"]
    assert config.pipelines[0].router() is None


def test_load_config_reports_route_errors(tmp_path: Path) -> None:
    path = tmp_path / "obsei.yaml"
    pipeline = pipeline_config(route=[{"when": {"classify.intent": ["bug"]}, "sinks": ["nope"]}])
    path.write_text(json.dumps({"version": 1, "pipelines": [pipeline]}), encoding="utf-8")
    with pytest.raises(ConfigError, match="route 1: no sink with key"):
        load_config(path)


def _answers(text: str) -> Json:
    intent = "billing" if "charged" in text else "bug"
    unsure = "maybe" in text
    urgent = "now" in text
    return {
        "sentiment": {
            "type": "choice",
            "choice": "negative",
            "probabilities": {"negative": 0.9, "positive": 0.1},
            "confidence": 0.9,
        },
        "intent": {
            "type": "choice",
            "choice": intent,
            "probabilities": {intent: 0.5 if unsure else 0.95},
            "confidence": 0.3 if unsure else 0.95,
        },
        "urgency": {
            "type": "score",
            "score": 3.0 if urgent else 0.2,
            "probabilities": {"3": 0.9, "0": 0.1} if urgent else {"0": 0.9, "3": 0.1},
            "confidence": 0.9,
        },
        "refund": {"type": "noul", "noul": 0.9 if intent == "billing" else 0.05},
    }


def test_routes_from_config_deliver_through_real_sinks(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ONCALL_URL", "https://hooks.slack.com/services/T/B/ONCALL")
    monkeypatch.setenv("BILLING_URL", "https://hooks.slack.com/services/T/B/BILLING")
    monkeypatch.setenv("REVIEW_URL", "https://hooks.slack.com/services/T/B/REVIEW")
    monkeypatch.setenv("JIRA_EMAIL", "bot@acme.test")
    monkeypatch.setenv("JIRA_API_TOKEN", "t")
    csv = tmp_path / "tickets.csv"
    csv.write_text(
        "id,created_at,text\n"
        "1,2026-09-01T08:00:00Z,checkout is down right now\n"
        "2,2026-09-01T09:00:00Z,I was charged twice\n"
        "3,2026-09-01T10:00:00Z,maybe the export is wrong\n"
        "4,2026-09-01T11:00:00Z,the logo looks blurry\n",
        encoding="utf-8",
    )
    lake = tmp_path / "lake"
    config = ObseiConfig.model_validate(
        {
            "version": 1,
            "llms": {"julia": {"api": "decision", "url": DECISION_URL}},
            "pipelines": [
                {
                    "name": "tickets",
                    "sources": [
                        {
                            "key": "csv",
                            "type": "csv",
                            "config": {
                                "path": str(csv),
                                "fields": {"text": "text", "id": "id", "created_at": "created_at"},
                            },
                        }
                    ],
                    "enrichers": [CLASSIFY],
                    "sinks": [
                        {
                            "key": "jira",
                            "type": "jira",
                            "config": {
                                "base_url": "https://acme.atlassian.net",
                                "project_key": "SUP",
                                "when": {},
                            },
                        },
                        {
                            "key": "oncall",
                            "type": "slack",
                            "config": {"webhook_url_env": "ONCALL_URL"},
                        },
                        {
                            "key": "billing",
                            "type": "slack",
                            "config": {"webhook_url_env": "BILLING_URL"},
                        },
                        {
                            "key": "review",
                            "type": "slack",
                            "config": {"webhook_url_env": "REVIEW_URL"},
                        },
                        {"key": "lake", "type": "parquet", "config": {"directory": str(lake)}},
                    ],
                    "route": [
                        {"review": ["review"]},
                        {
                            "name": "urgent-bugs",
                            "when": {
                                "classify.intent": {"is": "bug", "min_confidence": 0.8},
                                "classify.fields.urgency": {"gte": "today"},
                            },
                            "sinks": ["jira", "oncall"],
                        },
                        {
                            "name": "billing",
                            "when": {
                                "classify.intent": ["billing"],
                                "classify.fields.refund": {"is": True},
                            },
                            "sinks": ["billing"],
                        },
                        {"default": ["lake"]},
                    ],
                }
            ],
        }
    )
    posts: dict[str, list[str]] = {}
    issues: list[Json] = []

    def sinks(request: httpx.Request) -> httpx.Response:
        if request.url.host == "hooks.slack.com":
            posts.setdefault(request.url.path.rsplit("/", 1)[-1], []).append(
                json.loads(request.content)["text"]
            )
            return httpx.Response(200)
        if request.url.path.endswith("/search/jql"):
            return httpx.Response(200, json={"issues": []})
        issues.append(json.loads(request.content))
        return httpx.Response(201, json={"key": "SUP-1"})

    def decide(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"answers": _answers(json.loads(request.content)["state"])})

    ctx = Context(
        http=httpx.Client(transport=httpx.MockTransport(sinks)),
        egress=EgressPolicy(mode="hybrid"),
        llms=config.llms,
        llm_transport=httpx.MockTransport(decide),
    )
    store = Store(allow_unencrypted=True)
    report = run(build_pipeline(config, "tickets", ctx), store)

    assert [i["fields"]["summary"] for i in issues] == ["[bug] checkout is down right now"]
    assert [p.splitlines()[1] for p in posts["ONCALL"]] == ["> checkout is down right now"]
    assert [p.splitlines()[1] for p in posts["BILLING"]] == ["> I was charged twice"]
    assert [p.splitlines()[1] for p in posts["REVIEW"]] == ["> maybe the export is wrong"]
    assert report.sent == {"jira": 1, "oncall": 1, "billing": 1, "review": 1, "lake": 1}
    rows = duckdb.execute(
        "SELECT text, json_extract_string(enrichments, '$.enrichments.route.value.rule') "
        "FROM read_parquet(?)",
        [f"{lake}/*.parquet"],
    ).fetchall()
    assert rows == [("the logo looks blurry", "default")]
    counts = {r.key: r.count for r in store.stats(Query(), "route")}
    assert counts == {"review": 1, "urgent-bugs": 1, "billing": 1, "default": 1}


class _Levels(BaseModel):
    levels: dict[str, list[str]]


def test_classify_results_store_score_levels() -> None:
    from obsei.enrichers import ClassifyPluginConfig  # noqa: PLC0415
    from obsei.enrichers.classify import build_classifier  # noqa: PLC0415

    ctx = Context(
        llms={"julia": LlmEndpoint(api="decision", url=DECISION_URL)},
        llm_transport=httpx.MockTransport(
            lambda r: httpx.Response(200, json={"answers": _answers("now")})
        ),
    )
    classifier = build_classifier(ClassifyPluginConfig.model_validate(CLASSIFY["config"]), ctx)
    (result,) = classifier.enrich([rec()])
    assert result is not None
    assert _Levels.model_validate(result.value).levels == {"urgency": LEVELS}
    assert when({"classify.fields.urgency": {"gte": "today"}}).matches(rec(result))
