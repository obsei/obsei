import json
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path

from starlette.testclient import TestClient

from obsei.config import ObseiConfig
from obsei.core.context import Context
from obsei.runner import Scheduler, run_pipelines
from obsei.serve import create_app
from obsei.store import Store

NOW = datetime(2026, 10, 1, tzinfo=UTC)


TOKEN = "api-token-0123456789"


def config(tmp_path: Path) -> ObseiConfig:
    good = tmp_path / "good.csv"
    good.write_text("id,text\n1,Lento\n2,遅い\n", encoding="utf-8")
    source = {"key": "s", "type": "csv"}
    return ObseiConfig.model_validate(
        {
            "privacy": {"redact": True},
            "themes": {"auto": True, "k_anonymity": 1},
            "pipelines": [
                {
                    "name": "broken",
                    "every_minutes": 5,
                    "sources": [{**source, "config": {"path": str(tmp_path / "missing.csv")}}],
                },
                {
                    "name": "good",
                    "every_minutes": 60,
                    "sources": [{**source, "config": {"path": str(good)}}],
                },
                {"name": "manual", "sources": [{**source, "config": {"path": str(good)}}]},
            ],
        }
    )


def test_one_failing_pipeline_does_not_stop_the_others(tmp_path: Path) -> None:
    with Store(allow_unencrypted=True) as store:
        outcomes = run_pipelines(config(tmp_path), Context(), store, ["broken", "good"])
        assert [o.ok for o in outcomes] == [False, True]
        assert "missing.csv" in (outcomes[0].error or "")
        assert outcomes[1].summary().startswith("good: fetched 2, stored 2")
        assert store.count() == 2


def test_scheduler_runs_due_pipelines_and_themes(tmp_path: Path) -> None:
    store = Store(allow_unencrypted=True)

    @contextmanager
    def lease() -> Iterator[Store]:
        yield store

    scheduler = Scheduler(config(tmp_path), Context(), lease)
    assert scheduler.scheduled() == {"broken": 5, "good": 60}
    first = scheduler.run_due(NOW)
    assert {o.pipeline for o in first} == {"broken", "good"}
    assert store.theme_summaries(min_size=1)
    assert scheduler.run_due(NOW + timedelta(minutes=10))[0].pipeline == "broken"
    assert {o.pipeline for o in scheduler.run_due(NOW + timedelta(minutes=61))} == {
        "broken",
        "good",
    }


def test_serve_reports_runs(tmp_path: Path) -> None:
    cfg = config(tmp_path)
    store = Store(allow_unencrypted=True)
    web = create_app(cfg, Context(), store, token=TOKEN)
    web.state.scheduler.run_due(NOW)
    body = (
        TestClient(web, base_url="http://127.0.0.1:8765")
        .get("/api/runs", headers={"Authorization": f"Bearer {TOKEN}"})
        .json()
    )
    assert body["scheduled"] == {"broken": 5, "good": 60}
    assert body["last"]["good"]["ok"] is True
    assert body["last"]["broken"]["ok"] is False
    assert json.dumps(body)
