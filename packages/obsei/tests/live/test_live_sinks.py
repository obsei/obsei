"""Sinks against real sandbox workspaces. Each test is skipped unless its secrets are set."""

import os
from collections.abc import Iterator
from datetime import UTC, datetime
from uuid import uuid4

import pytest

from obsei import Enrichment, Record, SourceRef
from obsei.core.context import Context, default_http
from obsei.core.protocols import Sink
from obsei.core.registry import Registry
from obsei.llm import EgressPolicy
from obsei.privacy.redact import RegexRedactor
from obsei.sinks import register

SLACK = "OBSEI_LIVE_SLACK_WEBHOOK"
LINEAR_KEY = "OBSEI_LIVE_LINEAR_API_KEY"
LINEAR_TEAM = "OBSEI_LIVE_LINEAR_TEAM_ID"


@pytest.fixture(scope="module")
def ctx() -> Iterator[Context]:
    with Context(http=default_http(), egress=EgressPolicy(mode="hybrid")) as context:
        yield context


def sink(name: str, config: dict[str, object], ctx: Context) -> Sink:
    registry = Registry()
    register(registry)
    return registry.sink(name).create(config, ctx)  # type: ignore[arg-type]


def record() -> Record:
    raw = Record(
        source=SourceRef(type="live-check", native_id=uuid4().hex),
        text="obsei live check: export crashes on start. Reach me at jane.doe@example.com",
        created_at=datetime.now(UTC),
        enrichments={"classify": Enrichment(value={"intent": "bug"})},
    )
    (redacted,) = RegexRedactor().redact([raw])
    assert "jane.doe@example.com" not in redacted.text
    return redacted


@pytest.mark.skipif(not os.environ.get(SLACK), reason=f"set {SLACK} to a sandbox webhook")
def test_slack(ctx: Context) -> None:
    result = sink("slack", {"webhook_url_env": SLACK}, ctx).send([record()])
    assert (result.sent, result.errors) == (1, [])


@pytest.mark.skipif(
    not (os.environ.get(LINEAR_KEY) and os.environ.get(LINEAR_TEAM)),
    reason=f"set {LINEAR_KEY} and {LINEAR_TEAM} for a sandbox team",
)
def test_linear_creates_once(ctx: Context) -> None:
    linear = sink("linear", {"team_id": os.environ[LINEAR_TEAM], "api_key_env": LINEAR_KEY}, ctx)
    item = record()
    first = linear.send([item])
    assert (first.sent, first.errors) == (1, [])
    again = linear.send([item])
    assert (again.sent, again.skipped, again.errors) == (0, 1, [])
