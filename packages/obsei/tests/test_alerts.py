import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import pytest
import yaml
from typer.testing import CliRunner

from obsei import Author, Enrichment, Record, SourceRef
from obsei.alerts import alert_sinks, check_alerts, spike
from obsei.cli import app
from obsei.config import AlertConfig, ConfigError, ObseiConfig, builtin_registry
from obsei.core.context import Context
from obsei.core.protocols import Alert, EventDelivery
from obsei.llm import EgressPolicy
from obsei.runner import Scheduler
from obsei.sinks import webhook
from obsei.sinks.notify import NotifyConfig, NotifySink
from obsei.sinks.slack import render_alert
from obsei.store import Store, ThemeSummary

NOW = datetime(2026, 10, 1, tzinfo=UTC)
HYBRID = EgressPolicy(mode="hybrid")
HOOK = {"type": "webhook", "config": {"url": "http://hooks.internal/alerts"}}
STEADY = [5] * 8
SPIKE = [2, 3, 2, 3, 2, 3, 2, 15]


def summary(weekly: list[int]) -> ThemeSummary:
    return ThemeSummary(
        id="thm_1",
        label="Login",
        description=None,
        size=sum(weekly),
        duplicates=0,
        avg_rating=None,
        last_7_days=weekly[-1],
        previous_7_days=weekly[-2],
        weekly=weekly,
    )


@pytest.mark.parametrize(
    ("weekly", "fires"),
    [
        (SPIKE, True),
        (STEADY, False),
        ([0, 0, 0, 0, 0, 0, 1, 4], False),
        ([0, 20, 0, 20, 0, 20, 0, 20], False),
        ([10, 10, 10, 10, 10, 10, 12, 20], False),
    ],
    ids=["spike", "steady", "low-volume", "noisy", "not-double"],
)
def test_spike_statistic(weekly: list[int], fires: bool) -> None:
    assert (spike(summary(weekly), 2.0, 5) is not None) == fires


def test_rising_is_studios_rule() -> None:
    assert summary([0, 0, 0, 0, 0, 0, 1, 3]).rising
    assert not summary([0, 0, 0, 0, 0, 0, 0, 2]).rising
    assert not summary([0, 0, 0, 0, 0, 0, 5, 9]).rising


def add_theme(
    store: Store,
    name: str,
    weekly: list[int],
    *,
    people: int = 100,
    at: datetime = NOW,
    **data: object,
) -> str:
    records = [
        Record(
            source=SourceRef(type="appstore", native_id=f"{name}-{week}-{i}"),
            text=f"{name} broken\nagain {week} {i}",
            created_at=at - timedelta(days=7 * (len(weekly) - 1 - week) + 1, minutes=i),
            author=Author(pseudonym=f"psn_{name.encode().hex()[:16]:0<16}{i % people:016x}"),
            **data,
        )
        for week, count in enumerate(weekly)
        for i in range(count)
    ]
    store.upsert(records)
    theme_id = f"thm_{name}"
    store.save_theme(theme_id, "m", [1.0], len(records))
    store.label_theme(theme_id, name, None)
    for record in records:
        store.assign(record.id, theme_id, 1.0, None)
    return theme_id


def config(*alerts: dict[str, object], k: int = 3) -> ObseiConfig:
    source = {"key": "s", "type": "csv", "config": {"path": "feedback.csv"}}
    return ObseiConfig.model_validate(
        {
            "themes": {"k_anonymity": k},
            "pipelines": [{"name": "reviews", "sources": [source]}],
            "alerts": list(alerts),
        }
    )


class Hook:
    def __init__(self) -> None:
        self.events: list[dict[str, object]] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.events.append(json.loads(request.content))
        return httpx.Response(204)

    def context(self) -> Context:
        return Context(http=httpx.Client(transport=httpx.MockTransport(self)), egress=HYBRID)


@pytest.fixture
def store() -> Store:
    return Store(allow_unencrypted=True)


def test_spike_alert_is_k_anonymous_and_logged(store: Store) -> None:
    spiking = add_theme(store, "login", SPIKE)
    add_theme(store, "steady", STEADY)
    add_theme(store, "private", SPIKE, people=2)
    hook = Hook()
    cfg = config({"name": "spikes", "kind": "theme_spike", "owner": "@ana", "to": [HOOK]})
    fired = check_alerts(cfg, hook.context(), store, now=NOW)
    assert [(f.alert.key, f.errors) for f in fired] == [(spiking, [])]
    (event,) = hook.events
    assert (event["type"], event["source"]) == (
        "obsei.theme.spiking",
        "obsei/alerts/spikes/webhook",
    )
    data = event["data"]
    assert isinstance(data, dict)
    assert (data["count"], data["baseline"], data["theme"]) == (15, 2.43, spiking)
    assert data["lines"][-1] == "Owner: @ana"
    assert len(data["quotes"]) == 3
    assert all("\n" not in q for q in data["quotes"])
    assert "psn_" not in json.dumps(event)
    (delivery,) = store.deliveries()
    assert (delivery.pipeline, delivery.sink, delivery.event_type) == (
        "alerts/spikes",
        "webhook",
        "obsei.theme.spiking",
    )


def test_spikes_fire_once_a_week_by_default(store: Store) -> None:
    add_theme(store, "login", SPIKE)
    hook = Hook()
    cfg = config({"name": "spikes", "kind": "theme_spike", "to": [HOOK]})
    assert len(check_alerts(cfg, hook.context(), store, now=NOW)) == 1
    assert check_alerts(cfg, hook.context(), store, now=NOW + timedelta(hours=167)) == []
    later = config({"name": "spikes", "kind": "theme_spike", "to": [HOOK], "cooldown_hours": 24})
    assert len(check_alerts(later, hook.context(), store, now=NOW + timedelta(hours=24))) == 1


def test_cooldown_snooze_and_ack(store: Store) -> None:
    theme = add_theme(store, "login", SPIKE)
    hook = Hook()
    cfg = config({"name": "spikes", "kind": "theme_spike", "to": [HOOK], "cooldown_hours": 12})

    def fire(at: datetime) -> int:
        return len(check_alerts(cfg, hook.context(), store, now=at))

    assert fire(NOW) == 1
    assert fire(NOW + timedelta(hours=11)) == 0
    assert fire(NOW + timedelta(hours=12)) == 1
    (state,) = store.alert_states()
    assert state.key == theme
    later = NOW + timedelta(days=1)
    store.put_alert_state(state.model_copy(update={"snoozed_until": later + timedelta(hours=1)}))
    assert fire(later) == 0
    store.put_alert_state(state.model_copy(update={"acked_by": "ana", "acked_at": NOW}))
    assert fire(later) == 0
    store.put_alert_state(state.model_copy(update={"acked_at": later - timedelta(days=7)}))
    assert check_alerts(cfg, hook.context(), store, now=later, dry_run=True)
    assert len(hook.events) == 2


def test_new_theme_fires_once(store: Store) -> None:
    fresh = add_theme(store, "fresh", [0, 0, 0, 0, 0, 0, 0, 4])
    add_theme(store, "old", [1, 0, 0, 0, 0, 0, 0, 4])
    hook = Hook()
    cfg = config({"name": "new", "kind": "new_theme", "to": [HOOK]})
    assert [f.alert.key for f in check_alerts(cfg, hook.context(), store, now=NOW)] == [fresh]
    assert check_alerts(cfg, hook.context(), store, now=NOW + timedelta(days=3)) == []
    assert hook.events[0]["type"] == "obsei.theme.new"


def test_digest_lists_top_themes_once_per_period(store: Store) -> None:
    add_theme(store, "login", SPIKE)
    add_theme(store, "billing", STEADY)
    add_theme(store, "small", [0, 0, 0, 0, 0, 0, 0, 3])
    hook = Hook()
    cfg = config({"name": "weekly", "kind": "digest", "to": [HOOK], "top": 2})
    (fired,) = check_alerts(cfg, hook.context(), store, now=NOW)
    assert fired.alert.lines == ["23 records", "login: 15 (rising)", "billing: 5"]
    assert check_alerts(cfg, hook.context(), store, now=NOW + timedelta(days=6)) == []
    assert len(check_alerts(cfg, hook.context(), store, now=NOW + timedelta(days=7))) == 1


def test_review_queue(store: Store) -> None:
    flagged = Enrichment(value={"intent": "bug", "review": True})
    add_theme(store, "unsure", [0, 0, 0, 0, 0, 0, 0, 3], enrichments={"classify": flagged})
    hook = Hook()
    quiet = config({"name": "queue", "kind": "review_queue", "to": [HOOK]})
    assert check_alerts(quiet, hook.context(), store, now=NOW) == []
    busy = config({"name": "queue", "kind": "review_queue", "to": [HOOK], "min_pending": 3})
    (fired,) = check_alerts(busy, hook.context(), store, now=NOW)
    assert (fired.alert.title, hook.events[0]["type"]) == (
        "3 records await review",
        "obsei.review.pending",
    )


def test_pipeline_health_failures_and_stale_sources(store: Store) -> None:
    store.set_cursor("reviews", "s", {"page": 1})
    store.set_cursor("removed", "s", {"page": 1})
    hook = Hook()
    cfg = config({"name": "health", "kind": "pipeline_health", "to": [HOOK], "stale_hours": 24})
    later = datetime.now(UTC) + timedelta(hours=25)
    fired = check_alerts(cfg, hook.context(), store, failures={"reviews": "boom"}, now=later)
    assert [(f.alert.key, f.alert.title) for f in fired] == [
        ("reviews", "Pipeline reviews failed"),
        ("reviews/s", "Source reviews/s fetched nothing for 24 h"),
    ]
    assert check_alerts(cfg, hook.context(), store, failures={"reviews": "boom"}, now=later) == []
    assert {e["type"] for e in hook.events} == {"obsei.pipeline.failed"}


def test_scheduler_checks_alerts_after_each_run(tmp_path: Path, store: Store) -> None:
    hook = Hook()
    cfg = ObseiConfig.model_validate(
        {
            "pipelines": [
                {
                    "name": "broken",
                    "every_minutes": 5,
                    "sources": [
                        {"key": "s", "type": "csv", "config": {"path": str(tmp_path / "no.csv")}}
                    ],
                }
            ],
            "alerts": [{"name": "health", "kind": "pipeline_health", "to": [HOOK]}],
        }
    )
    Scheduler(cfg, hook.context(), store).run_due(NOW)
    (event,) = hook.events
    data = event["data"]
    assert isinstance(data, dict)
    assert data["key"] == "broken"
    assert "no.csv" in data["lines"][0]


def test_alert_targets_are_validated(monkeypatch: pytest.MonkeyPatch) -> None:
    with pytest.raises(ValueError, match="alert names must be unique"):
        config(
            {"name": "a", "kind": "digest", "to": [HOOK]},
            {"name": "a", "kind": "digest", "to": [HOOK]},
        )
    with pytest.raises(ValueError, match="give sinks of the same type a key"):
        config({"name": "a", "kind": "digest", "to": [HOOK, HOOK]})
    with pytest.raises(ValueError, match="kind"):
        config({"name": "a", "kind": "sometimes", "to": [HOOK]})
    with pytest.raises(ValueError, match="to"):
        config({"name": "a", "kind": "digest", "to": []})
    monkeypatch.setenv("JIRA_EMAIL", "a@acme.com")
    monkeypatch.setenv("JIRA_API_TOKEN", "t")
    jira = {
        "type": "jira",
        "config": {"base_url": "https://acme.atlassian.net", "project_key": "VOC"},
    }
    alert = AlertConfig.model_validate({"name": "a", "kind": "digest", "to": [jira]})
    with pytest.raises(ConfigError, match="jira sinks cannot deliver alerts"):
        alert_sinks(alert, Context(egress=HYBRID), builtin_registry())
    bad = AlertConfig.model_validate(
        {"name": "a", "kind": "digest", "to": [{"type": "webhook", "config": {}}]}
    )
    with pytest.raises(ConfigError, match="alert 'a', sink 'webhook'"):
        alert_sinks(bad, Context(egress=HYBRID), builtin_registry())


ALERT = Alert(
    alert="spikes",
    kind="theme_spike",
    key="thm_1",
    title="Theme spiking: <Login>",
    lines=["15 records", "Owner: @ana"],
    quotes=["I <EMAIL> cannot log in"],
)


def test_slack_posts_one_escaped_message(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SLACK_WEBHOOK_URL", "https://hooks.slack.com/services/T/B/X")
    posts: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        posts.append(json.loads(request.content)["text"])
        return httpx.Response(200)

    alert = AlertConfig.model_validate(
        {"name": "a", "kind": "theme_spike", "to": [{"type": "slack"}]}
    )
    ctx = Context(http=httpx.Client(transport=httpx.MockTransport(handler)), egress=HYBRID)
    ((_, sink),) = alert_sinks(alert, ctx, builtin_registry())
    assert sink.alert(ALERT).sent == 1
    assert posts == [render_alert(ALERT)]
    assert posts[0] == (
        "*Theme spiking: &lt;Login&gt;*\n15 records\nOwner: @ana\n> I &lt;EMAIL&gt; cannot log in"
    )


def test_notify_sends_one_notification(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APPRISE_URLS", "json://alerts.internal/obsei")
    sink = NotifySink(NotifyConfig(), Context(egress=HYBRID))
    sent: list[dict[str, str]] = []

    def notify(**message: str) -> bool:
        sent.append(message)
        return True

    monkeypatch.setattr(sink.targets[0], "notify", notify)
    assert sink.alert(ALERT).sent == 1
    assert sent == [
        {
            "title": "Theme spiking: <Login>",
            "body": "15 records\nOwner: @ana\n> I <EMAIL> cannot log in",
        }
    ]


def write_config(tmp_path: Path, alerts: list[dict[str, object]]) -> Path:
    path = tmp_path / "obsei.yaml"
    source = {"key": "s", "type": "csv", "config": {"path": "feedback.csv"}}
    path.write_text(
        yaml.safe_dump(
            {
                "store": {"path": str(tmp_path / "obsei.duckdb"), "unencrypted": True},
                "themes": {"k_anonymity": 3},
                "pipelines": [{"name": "reviews", "sources": [source]}],
                "alerts": alerts,
            }
        ),
        encoding="utf-8",
    )
    return path


def test_cli_check_list_snooze_and_ack(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OBSEI_DB_KEY", raising=False)
    with Store(tmp_path / "obsei.duckdb", allow_unencrypted=True) as store:
        theme = add_theme(store, "login", [0, 0, 0, 0, 0, 0, 0, 12], at=datetime.now(UTC))
    path = write_config(
        tmp_path,
        [
            {"name": "spikes", "kind": "theme_spike", "to": [HOOK]},
            {"name": "queue", "kind": "review_queue", "to": [HOOK]},
        ],
    )
    emitted: list[str] = []

    def emit(self: webhook.WebhookSink, event_type: str, data: object) -> EventDelivery:
        emitted.append(event_type)
        return EventDelivery(event_id="evt_1", event_type=event_type, host="h", attempts=1)

    monkeypatch.setattr(webhook.WebhookSink, "emit", emit)

    def run(*args: str) -> str:
        return CliRunner().invoke(app, ["alerts", *args, "-c", str(path)]).output

    dry = run("check", "--dry-run")
    assert f"would fire spikes {theme}: Theme spiking: login" in dry
    assert "12 records in the last 7 days" in dry
    assert emitted == []
    assert f"alert spikes {theme}" in run("check")
    assert emitted == ["obsei.theme.spiking"]
    listed = run("list")
    assert "queue  -  never fired" in listed
    assert f"spikes  {theme}  fired" in listed
    assert "snoozed spikes" in run("snooze", "spikes", theme, "--hours", "2")
    assert "acknowledged" in run("ack", "spikes", theme, "--by", "ana")
    assert "acked by ana" in run("list")
    result = CliRunner().invoke(app, ["alerts", "ack", "nope", "x", "-c", str(path)])
    assert result.exit_code == 2
    assert "no alert named 'nope'" in result.output
