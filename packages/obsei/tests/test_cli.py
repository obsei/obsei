import json

import pytest
from typer.testing import CliRunner

from obsei import __version__
from obsei.cli import app

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
