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
