import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
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


def test_forget_requires_a_filter_and_a_key(db: Path) -> None:
    assert runner.invoke(app, ["forget", "--db", str(db), "--unencrypted"]).exit_code == 2
    result = runner.invoke(app, ["forget", "--source", "csv", "--db", str(db)])
    assert result.exit_code == 2
    assert "encryption key is required" in result.output
