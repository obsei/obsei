import json
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from packaging.version import Version
from typer.testing import CliRunner

from obsei import Author, Record, SourceRef, __version__
from obsei.cli import app
from obsei.privacy import pseudonymize
from obsei.store import Store

runner = CliRunner()


def test_version_command_and_flag() -> None:
    for args in (["version"], ["--version"]):
        result = runner.invoke(app, args)
        assert result.exit_code == 0
        assert __version__ in result.output


def test_doctor_reports_missing_salt(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OBSEI_PSEUDONYM_SALT", raising=False)
    result = runner.invoke(app, ["doctor"])
    assert result.exit_code == 0
    assert "not set" in result.output
    assert "duckdb" in result.output
    assert "egress    air_gapped" in result.output


def test_schema_is_valid_json() -> None:
    result = runner.invoke(app, ["schema"])
    assert result.exit_code == 0
    schema = json.loads(result.output)
    assert schema["title"] == "Record"
    assert "content_hash" in schema["properties"]


SALT = "0123456789abcdef-test-salt"


@pytest.fixture
def db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("OBSEI_PSEUDONYM_SALT", SALT)
    monkeypatch.delenv("OBSEI_DB_KEY", raising=False)
    path = tmp_path / "obsei.duckdb"
    author = Author(pseudonym=pseudonymize("@alice", SALT.encode()))
    old = datetime.now(UTC) - timedelta(days=400)
    with Store(path, allow_unencrypted=True) as store:
        store.upsert(
            [
                Record(source=SourceRef(type="csv", native_id="1"), text="a", created_at=old),
                Record(
                    source=SourceRef(type="csv", native_id="2"),
                    text="b",
                    created_at=datetime.now(UTC),
                    author=author,
                ),
            ]
        )
    return path


def test_export_author(db: Path) -> None:
    result = runner.invoke(app, ["export", "--author", "@Alice", "--db", str(db), "--unencrypted"])
    assert result.exit_code == 0, result.output
    (line,) = result.output.strip().splitlines()
    assert Record.model_validate_json(line).text == "b"


def test_forget_author_and_retention(db: Path) -> None:
    args = ["--db", str(db), "--unencrypted"]
    result = runner.invoke(app, ["forget", "--author", "@alice", *args])
    assert "deleted 1 record(s)" in result.output
    result = runner.invoke(app, ["forget", "--older-than-days", "365", *args])
    assert "deleted 1 record(s)" in result.output
    with Store(db, allow_unencrypted=True) as store:
        assert store.count() == 0
    log = runner.invoke(app, ["audit", *args]).output
    assert log.count("forget") == 2
    assert "alice" not in log
    assert '"deleted": 1' in log


def test_forget_requires_a_filter_and_a_key(db: Path) -> None:
    assert runner.invoke(app, ["forget", "--db", str(db), "--unencrypted"]).exit_code == 2
    result = runner.invoke(app, ["forget", "--source", "csv", "--db", str(db)])
    assert result.exit_code == 2
    assert "encryption key is required" in result.output


def test_init_then_try(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    created = runner.invoke(app, ["init"])
    assert created.exit_code == 0
    assert (tmp_path / "obsei.yaml").exists()
    assert "skip" in runner.invoke(app, ["init"]).output
    preview = runner.invoke(app, ["try", "--limit", "2"])
    assert preview.exit_code == 0, preview.output
    lines = [json.loads(line) for line in preview.output.splitlines()]
    assert [line["lang"] for line in lines] == ["en", "es"]


def test_run_reports_missing_config(tmp_path: Path) -> None:
    result = runner.invoke(app, ["run", "--config", str(tmp_path / "nope.yaml")])
    assert result.exit_code == 2
    assert "obsei init" in result.output


def test_core_cli_works_without_optional_extras() -> None:
    code = (
        "import sys\n"
        "for name in ('mcp', 'starlette', 'uvicorn', 'sqlalchemy', 'jwt', 'google'):\n"
        "    sys.modules[name] = None\n"
        "from obsei.cli import app\n"
        "from obsei import ask, config, studio, themes\n"
    )
    subprocess.run([sys.executable, "-c", code], check=True)  # noqa: S603


def test_version_is_a_release_version() -> None:
    """release-please rewrites only the semver part, so a suffix like .dev0 would ship."""
    assert not Version(__version__).is_devrelease


def offline_project(tmp_path: Path) -> Path:
    (tmp_path / "feedback.csv").write_text("id,text\n1,App crashes\n", encoding="utf-8")
    config = tmp_path / "obsei.yaml"
    config.write_text(
        f"""
store: {{path: {tmp_path / "obsei.duckdb"}, unencrypted: true}}
llms:
  default: {{base_url: "http://127.0.0.1:9/v1", model: qwen3:8b, timeout: 5}}
pipelines:
  - name: reviews
    sources:
      - {{key: csv, type: csv, config: {{path: {tmp_path / "feedback.csv"}}}}}
    enrichers:
      - {{type: classify, config: {{llm: default}}}}
""",
        encoding="utf-8",
    )
    return config


def _project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, k: int = 5) -> Path:
    """A project whose obsei.yaml keeps the store at data/voc.duckdb."""
    monkeypatch.setenv("OBSEI_PSEUDONYM_SALT", SALT)
    monkeypatch.delenv("OBSEI_DB_KEY", raising=False)
    monkeypatch.delenv("OBSEI_DB", raising=False)
    monkeypatch.delenv("OBSEI_CONFIG", raising=False)
    monkeypatch.chdir(tmp_path)
    (tmp_path / "data").mkdir()
    (tmp_path / "feedback.csv").write_text("id,text\n1,slow app\n2,crash\n", encoding="utf-8")
    config = tmp_path / "obsei.yaml"
    config.write_text(
        "store: {path: data/voc.duckdb, unencrypted: true}\n"
        f"themes: {{k_anonymity: {k}}}\n"
        "pipelines:\n"
        "  - name: p\n"
        "    sources:\n"
        "      - {key: s, type: csv, config: {path: feedback.csv}}\n",
        encoding="utf-8",
    )
    return config


def test_run_warns_when_the_classifier_model_is_unreachable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("OBSEI_PSEUDONYM_SALT", SALT)
    result = runner.invoke(app, ["run", "-c", str(offline_project(tmp_path))])
    assert result.exit_code == 0, result.output
    assert "enriched 0 (1 failed)" in result.output
    assert "warning: reviews: classify failed for 1 record(s)" in result.output
    assert "cannot reach the model at http://127.0.0.1:9/v1" in result.output
    assert "retried on the next run" in result.output
    with Store(tmp_path / "obsei.duckdb", allow_unencrypted=True) as store:
        assert len(store.retry_records("reviews", "csv", 10)) == 1


def test_ask_names_the_unreachable_endpoint(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("OBSEI_PSEUDONYM_SALT", SALT)
    config = offline_project(tmp_path)
    assert runner.invoke(app, ["run", "-c", str(config)]).exit_code == 0
    result = runner.invoke(app, ["ask", "what breaks?", "-c", str(config)])
    assert result.exit_code == 2
    assert "cannot reach the model at http://127.0.0.1:9/v1" in result.output
    assert "ollama serve" in result.output


def test_serve_honours_db_option(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import uvicorn  # noqa: PLC0415

    monkeypatch.setenv("OBSEI_PSEUDONYM_SALT", SALT)
    monkeypatch.setattr(uvicorn, "run", lambda *args, **kwargs: None)
    other = tmp_path / "elsewhere.duckdb"
    result = runner.invoke(app, ["serve", "-c", str(offline_project(tmp_path)), "--db", str(other)])
    assert result.exit_code == 0, result.output
    assert other.exists()
    assert not (tmp_path / "obsei.duckdb").exists()


def test_forget_export_and_audit_use_the_configured_store(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = _project(tmp_path, monkeypatch)
    assert runner.invoke(app, ["run", "-c", str(config)]).exit_code == 0
    result = runner.invoke(app, ["forget", "--source", "csv"])
    assert result.exit_code == 0, result.output
    assert "deleted 2 record(s)" in result.output
    assert runner.invoke(app, ["export", "--author", "@x", "-c", str(config)]).exit_code == 0
    assert "forget" in runner.invoke(app, ["audit", "--config", str(config)]).output
    assert not (tmp_path / "obsei.duckdb").exists()

    assert runner.invoke(app, ["run", "-c", str(config)]).exit_code == 0
    with Store(tmp_path / "data" / "voc.duckdb", allow_unencrypted=True) as store:
        assert store.count() == 0


def test_forget_export_and_audit_never_create_a_store(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("OBSEI_PSEUDONYM_SALT", SALT)
    monkeypatch.chdir(tmp_path)
    missing = tmp_path / "missing.duckdb"
    for args in (
        ["forget", "--source", "csv"],
        ["export", "--author", "@x"],
        ["audit"],
        ["forget", "--source", "csv", "--db", str(missing)],
    ):
        result = runner.invoke(app, [*args, "--unencrypted"])
        assert result.exit_code == 2, args
        assert "no obsei store" in result.output
    assert not (tmp_path / "obsei.duckdb").exists()
    assert not missing.exists()
    missing_config = runner.invoke(app, ["audit", "-c", str(tmp_path / "nope.yaml")])
    assert missing_config.exit_code == 2
    assert "not found" in missing_config.output


def test_mcp_uses_the_configured_k_anonymity(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pytest.importorskip("mcp")
    from obsei import mcp_server  # noqa: PLC0415

    config = _project(tmp_path, monkeypatch, k=3)
    captured: dict[str, object] = {}

    class FakeServer:
        def run(self, transport: str) -> None:
            captured["transport"] = transport

    def fake_create_server(opener: object, *, k_anonymity: int = 5) -> FakeServer:
        captured["k"] = k_anonymity
        return FakeServer()

    monkeypatch.setattr(mcp_server, "create_server", fake_create_server)
    result = runner.invoke(app, ["mcp", "-c", str(config)])
    assert result.exit_code == 0, result.output
    assert captured == {"k": 3, "transport": "stdio"}


def test_doctor_explains_air_gapped_extension_preinstall(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("OBSEI_DUCKDB_EXTENSIONS", str(tmp_path))
    monkeypatch.setenv("OBSEI_EGRESS_MODE", "air_gapped")
    result = runner.invoke(app, ["doctor"])
    assert result.exit_code == 0
    assert f"httpfs extension not installed in {tmp_path}" in result.output
    assert "never downloads" in result.output
