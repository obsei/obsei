import json
import threading
from datetime import UTC, datetime, timedelta
from pathlib import Path

import duckdb
import httpx
import pytest
from starlette.testclient import TestClient

from obsei import runner
from obsei.config import ObseiConfig
from obsei.core.context import Context
from obsei.pipeline import Pipeline, RunReport, run
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
    scheduler = Scheduler(config(tmp_path), Context(), store)
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
    assert "missing.csv" in body["last"]["broken"]["error"]
    assert body["last"]["good"]["warnings"] == []
    assert json.dumps(body)


@pytest.mark.parametrize(
    "error",
    [httpx.ConnectError("connection refused"), duckdb.IOException("disk I/O error")],
    ids=["http", "duckdb"],
)
def test_network_and_database_errors_are_isolated(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, error: Exception
) -> None:
    def flaky(pipeline: Pipeline, store: Store, **kwargs: object) -> RunReport:
        if pipeline.name == "manual":
            raise error
        return run(pipeline, store)

    monkeypatch.setattr(runner, "run", flaky)
    with Store(allow_unencrypted=True) as store:
        outcomes = run_pipelines(config(tmp_path), Context(), store, ["manual", "good"])
    assert [o.ok for o in outcomes] == [False, True]
    assert str(error) in (outcomes[0].error or "")


def test_scheduler_loop_survives_unexpected_errors(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = threading.Semaphore(0)

    def boom(self: Scheduler, now: datetime | None = None) -> list[object]:
        calls.release()
        raise TypeError("plugin bug")

    monkeypatch.setattr(Scheduler, "run_due", boom)
    scheduler = Scheduler(config(tmp_path), Context(), Store(allow_unencrypted=True))
    scheduler.tick_seconds = 0.01
    scheduler.start()
    try:
        assert calls.acquire(timeout=5)
        assert calls.acquire(timeout=5)
        assert scheduler.healthy
        assert scheduler.last_error == "TypeError: plugin bug"
    finally:
        scheduler.stop()


def test_healthz_is_degraded_when_the_scheduler_died(tmp_path: Path) -> None:
    web = create_app(config(tmp_path), Context(), Store(allow_unencrypted=True), token=TOKEN)
    client = TestClient(web, base_url="http://127.0.0.1:8765")
    assert client.get("/healthz").status_code == 200
    dead = threading.Thread(target=lambda: None)
    dead.start()
    dead.join()
    web.state.scheduler._thread = dead
    response = client.get("/healthz")
    assert response.status_code == 503
    assert response.json() == {"status": "degraded", "scheduler": "stopped"}
    runs = client.get("/api/runs", headers={"Authorization": f"Bearer {TOKEN}"}).json()
    assert runs["scheduler"]["healthy"] is False
