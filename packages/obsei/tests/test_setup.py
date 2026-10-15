"""Guided setup: the integration catalog, obsei add, obsei check, the schema and plugin new."""

import json
import os
import re
from collections.abc import Callable, Iterator
from importlib import resources
from pathlib import Path
from unittest import mock

import httpx
import pytest
import yaml
from pydantic import BaseModel, JsonValue
from typer.testing import CliRunner

from obsei import catalog, cli, yamledit
from obsei.cli import app
from obsei.config import ObseiConfig, builtin_registry, load_config, parse_config, save_secrets
from obsei.core.context import Context
from obsei.core.plugin import Catalog
from obsei.llm.egress import EgressPolicy

runner = CliRunner()
ROOT = Path(__file__).resolve().parents[3]
DOCS = ROOT / "docs" / "src" / "content" / "docs"
SCHEMA_FILE = ROOT / "docs" / "public" / "schema" / "obsei.schema.json"
TEMPLATE_DOCS = "https://github.com/obsei/obsei/tree/master/plugins/template"
HOOK = "https://hooks.slack.com/services/T000/B000/secret-token"
Handler = Callable[[httpx.Request], httpx.Response]


@pytest.fixture(autouse=True)
def _environ(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setattr(cli, "find_spec", lambda name: None)
    with mock.patch.dict(os.environ):
        for name in ("SLACK_WEBHOOK_URL", "OBSEI_EGRESS_MODE", "OBSEI_EGRESS_ALLOW"):
            os.environ.pop(name, None)
        yield


@pytest.fixture
def project(tmp_path: Path) -> Path:
    assert runner.invoke(app, ["init", str(tmp_path), "--offline"]).exit_code == 0
    return tmp_path / "obsei.yaml"


def _slack(request: httpx.Request) -> httpx.Response:
    if json.loads(request.content) == {}:
        return httpx.Response(400, text="no_text")
    return httpx.Response(200, text="ok")


def _apple(request: httpx.Request) -> httpx.Response:
    if "page=1" not in request.url.path:
        return httpx.Response(200, json={"feed": {}})
    entry = {
        "id": {"label": "r1"},
        "im:rating": {"label": "1"},
        "title": {"label": "Login broken"},
        "content": {"label": "Call me on 090-1234-5678, I cannot log in."},
        "updated": {"label": "2026-09-02T10:00:00-07:00"},
    }
    return httpx.Response(200, json={"feed": {"entry": [entry]}})


def _feed(request: httpx.Request) -> httpx.Response:
    item = "<item><guid>1</guid><title>Great</title><description>Love it</description></item>"
    return httpx.Response(200, text=f"<rss><channel>{item}</channel></rss>")


def _http(monkeypatch: pytest.MonkeyPatch, handler: Handler) -> list[httpx.Request]:
    seen: list[httpx.Request] = []

    def record(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return handler(request)

    def context(cfg: ObseiConfig) -> Context:
        client = httpx.Client(transport=httpx.MockTransport(record))
        return Context(http=client, egress=cfg.egress or EgressPolicy.from_env())

    monkeypatch.setattr(cli, "build_context", context)
    return seen


def _in_order(lines: list[str], text: str) -> bool:
    remaining = iter(text.splitlines())
    return all(line in remaining for line in lines)


def _secrets(config: Path) -> dict[str, str]:
    path = config.parent / ".obsei" / "secrets.env"
    lines = path.read_text(encoding="utf-8").splitlines()
    return dict(line.split("=", 1) for line in lines if "=" in line and not line.startswith("#"))


def test_every_plugin_has_a_catalog_entry() -> None:
    registry, owners = catalog.installed()
    assert {"teams", "typeform", "reddit"} <= set(owners.values())
    for kind, name, plugin in registry.plugins():
        entry = plugin.catalog
        assert entry is not None, f"{kind} {name}"
        assert entry.docs_url.startswith("https://"), f"{kind} {name}"
        model = plugin.config_model
        needed = [
            f
            for f in catalog.secret_fields(model)
            if model.model_fields[f].is_required() or model.model_fields[f].default is not None
        ]
        if needed:
            assert (entry.help_url or "").startswith("https://"), f"{kind} {name}"
        assert set(entry.ask) <= set(model.model_fields), f"{kind} {name}"
        assert all(f.endswith("_env") for f in catalog.secret_fields(model)), f"{kind} {name}"


@pytest.mark.parametrize(("guide", "kind"), [("sources.md", "source"), ("sinks.md", "sink")])
def test_catalog_status_matches_the_docs(guide: str, kind: str) -> None:
    text = (DOCS / "guides" / guide).read_text(encoding="utf-8")
    documented = dict(re.findall(r"^\| `(\w+)`.*\| (verified|beta) \|$", text, re.MULTILINE))
    registry, _ = catalog.installed()
    listed = {
        name: plugin.catalog.status
        for k, name, plugin in registry.plugins()
        if k == kind and plugin.catalog and name in documented
    }
    assert listed == documented


def _undescribed(model: type[BaseModel]) -> list[str]:
    schema = model.model_json_schema()
    found = []
    for title, spec in [(model.__name__, schema), *schema.get("$defs", {}).items()]:
        found += [
            f"{title}.{n}"
            for n, p in spec.get("properties", {}).items()
            if not p.get("description")
        ]
    return found


def test_every_config_field_is_described() -> None:
    registry, _ = catalog.installed()
    missing = [f for _, _, p in registry.plugins() for f in _undescribed(p.config_model)]
    assert missing == []


def test_published_schema_covers_every_plugin_config() -> None:
    schema = catalog.config_schema(catalog.installed()[0])
    sinks = schema["$defs"]["SinkEntry"]
    by_type = {rule["if"]["properties"]["type"]["const"]: rule["then"] for rule in sinks["allOf"]}
    assert by_type["teams"] == {"properties": {"config": {"$ref": "#/$defs/TeamsConfig"}}}
    assert {"slack", "jira", "notify"} <= set(by_type)
    published = json.dumps(schema, indent=2, sort_keys=True) + "\n"
    assert SCHEMA_FILE.read_text(encoding="utf-8") == published, (
        "regenerate it: uv run obsei schema config > docs/public/schema/obsei.schema.json"
    )
    result = runner.invoke(app, ["schema", "config"])
    assert result.exit_code == 0
    assert result.stdout == published


def test_schema_validates_examples_and_catches_typos() -> None:
    jsonschema = pytest.importorskip("jsonschema")
    validator = jsonschema.Draft202012Validator(json.loads(SCHEMA_FILE.read_text("utf-8")))

    def errors(text: str) -> list[str]:
        data = json.loads(json.dumps(yaml.safe_load(text), default=str))
        return [e.message for e in validator.iter_errors(data)]

    for path in sorted((ROOT / "examples").rglob("*.yaml")):
        text = path.read_text(encoding="utf-8")
        assert text.startswith(f"# yaml-language-server: $schema={catalog.SCHEMA_URL}\n"), path
        assert errors(text) == [], path
    social = (ROOT / "examples" / "social-listening.yaml").read_text(encoding="utf-8")
    assert any("text_fromat" in e for e in errors(social.replace("text_format", "text_fromat")))


def test_integrations_filter_and_json() -> None:
    result = runner.invoke(app, ["integrations", "slack"])
    assert result.exit_code == 0
    assert "slack            sink     chat      verified Slack channel" in result.stdout
    assert "secrets SLACK_WEBHOOK_URL" in result.stdout
    assert "keys    https://docs.slack.dev/" in result.stdout
    assert "appstore" not in result.stdout
    listed = json.loads(
        runner.invoke(app, ["integrations", "--category", "reviews", "--json"]).stdout
    )
    assert {i["name"] for i in listed} == {"appstore", "appstoreconnect", "playstore"}
    teams = json.loads(runner.invoke(app, ["integrations", "teams", "--json"]).stdout)
    assert teams[0]["plugin"] == "teams"


def test_add_a_source_without_prompts_keeps_comments(
    project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    before = project.read_text(encoding="utf-8")
    requested = _http(monkeypatch, _apple)
    args = ["add", "appstore", "-c", str(project), "--yes"]
    result = runner.invoke(
        app,
        [*args, "--set", "app_id=284882215", "--set", "countries=jp, us"],
        env={"COLUMNS": "200"},
    )
    assert result.exit_code == 0, result.output
    assert "Call me on <PHONE>, I cannot log in." in result.stdout
    assert "added  source appstore to pipeline feedback" in result.stdout
    assert str(requested[0].url).startswith("https://itunes.apple.com/jp/")
    after = project.read_text(encoding="utf-8")
    assert _in_order(before.splitlines(), after)
    source = load_config(project).pipelines[0].sources[1]
    assert (source.key, source.config) == (
        "appstore",
        {"app_id": "284882215", "countries": ["jp", "us"]},
    )

    again = runner.invoke(app, [*args, "--set", "app_id=1", "--key", "ios"])
    assert again.exit_code == 0, again.output
    assert [s.key for s in load_config(project).pipelines[0].sources] == [
        "sample",
        "appstore",
        "ios",
    ]


def test_add_a_sink_stores_the_secret_outside_obsei_yaml_and_allows_egress(
    project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    requested = _http(monkeypatch, _slack)
    result = runner.invoke(
        app, ["add", "slack", "-c", str(project), "--yes", "--set", f"webhook_url={HOOK}"]
    )
    assert result.exit_code == 0, result.output
    assert "allow  egress to hooks.slack.com" in result.stdout
    assert "secret SLACK_WEBHOOK_URL in" in result.stdout
    text = project.read_text(encoding="utf-8")
    assert "secret-token" not in text
    config = load_config(project)
    assert config.egress == EgressPolicy(
        mode="private", allowed_hosts=frozenset({"hooks.slack.com"})
    )
    assert config.pipelines[0].sinks[1].config == {"webhook_url_env": "SLACK_WEBHOOK_URL"}
    assert _secrets(project)["SLACK_WEBHOOK_URL"] == HOOK
    assert [json.loads(r.content) for r in requested] == [{}]
    if os.name == "posix":
        assert (project.parent / ".obsei" / "secrets.env").stat().st_mode & 0o777 == 0o600

    other = runner.invoke(
        app, ["add", "slack", "-c", str(project), "--yes", "--set", f"webhook_url={HOOK}2"]
    )
    assert other.exit_code == 0, other.output
    sinks = load_config(project).pipelines[0].sinks
    assert (sinks[2].key, sinks[2].config) == (
        "slack_2",
        {"webhook_url_env": "SLACK_2_WEBHOOK_URL"},
    )
    assert _secrets(project)["SLACK_WEBHOOK_URL"] == HOOK


def test_add_asks_for_settings_and_hides_secrets(
    project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _http(monkeypatch, lambda r: _apple(r) if "itunes" in str(r.url) else _slack(r))
    source = runner.invoke(app, ["add", "appstore", "-c", str(project)], input="284882215\nus\n")
    assert source.exit_code == 0, source.output
    assert "app_id (The digits after 'id' in the app's App Store link):" in source.stdout
    assert (
        "countries (Storefronts as ISO 3166 alpha-2 codes, e.g. us, gb, de, jp) [us]:"
        in source.stdout
    )
    assert load_config(project).pipelines[0].sources[1].config == {"app_id": "284882215"}

    sink = runner.invoke(
        app, ["add", "slack", "--key", "oncall", "-c", str(project)], input=f"{HOOK}\ny\n"
    )
    assert sink.exit_code == 0, sink.output
    assert (
        "webhook_url: the Slack incoming webhook URL (hidden, saved as ONCALL_WEBHOOK_URL"
        in sink.stdout
    )
    assert HOOK not in sink.stdout
    assert "allow it? [Y/n]" in sink.stdout
    assert HOOK not in project.read_text(encoding="utf-8")
    assert _secrets(project)["ONCALL_WEBHOOK_URL"] == HOOK


def test_add_explains_what_is_missing(project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    before = project.read_text(encoding="utf-8")
    typo = runner.invoke(app, ["add", "slak", "-c", str(project)])
    assert typo.exit_code == 2
    assert "no source or sink named 'slak'; did you mean slack?" in typo.output
    unset = runner.invoke(app, ["add", "slack", "-c", str(project), "--yes"])
    assert unset.exit_code == 2
    assert (
        "SLACK_WEBHOOK_URL is not set: export it, or pass --set webhook_url=VALUE" in unset.output
    )
    both = runner.invoke(app, ["add", "github_issues", "-c", str(project), "--yes"])
    assert "pass --as source or --as sink" in both.output
    required = runner.invoke(app, ["add", "appstore", "-c", str(project), "--yes"])
    assert "appstore: app_id: Field required" in required.output
    unknown = runner.invoke(app, ["add", "rss", "-c", str(project), "--yes", "--set", "link=x"])
    assert "rss has no field link" in unknown.output
    _http(monkeypatch, lambda r: httpx.Response(404, text="no_service"))
    monkeypatch.setenv("SLACK_WEBHOOK_URL", HOOK)
    monkeypatch.setenv("OBSEI_EGRESS_MODE", "hybrid")
    revoked = runner.invoke(app, ["add", "slack", "-c", str(project), "--yes"])
    assert revoked.exit_code == 2
    assert "slack returned 404: no_service" in revoked.output
    assert "keys: https://docs.slack.dev/" in revoked.output
    assert project.read_text(encoding="utf-8") == before


def test_add_a_plugin_sink_allows_its_plugin(
    project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pytest.importorskip("obsei_teams")
    _http(monkeypatch, _slack)
    monkeypatch.setenv("OBSEI_EGRESS_MODE", "hybrid")
    url = "https://example.environment.api.powerplatform.com/workflows/1"
    result = runner.invoke(
        app, ["add", "teams", "-c", str(project), "--yes", "--set", f"webhook_url={url}"]
    )
    assert result.exit_code == 0, result.output
    config = load_config(project)
    assert config.plugins == ["teams"]
    assert config.pipelines[0].sinks[1].type == "teams"


def test_add_an_alert(project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _http(monkeypatch, _slack)
    monkeypatch.setenv("OBSEI_EGRESS_MODE", "hybrid")
    monkeypatch.setenv("SLACK_WEBHOOK_URL", HOOK)
    args = [
        "add",
        "alert",
        "-c",
        str(project),
        "--yes",
        "--set",
        "kind=digest",
        "--set",
        "to=slack",
    ]
    result = runner.invoke(app, args)
    assert result.exit_code == 0, result.output
    (alert,) = load_config(project).alerts
    assert (alert.name, alert.kind, alert.to[0].type) == ("digest", "digest", "slack")
    assert "SLACK_WEBHOOK_URL" not in _secrets(project)
    bad = runner.invoke(app, ["add", "alert", "-c", str(project), "--yes", "--set", "kind=often"])
    assert "alerts take --set kind=" in bad.output


def test_check_reports_each_source_and_sink(project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(project.parent)
    ok = runner.invoke(app, ["check", "-c", str(project)])
    assert ok.exit_code == 0, ok.output
    assert "✓ feedback/sample  source csv: fetched a record" in ok.stdout
    assert "✓ feedback/parquet  sink parquet: built (nothing sent)" in ok.stdout
    assert "all 2 ready" in ok.stdout

    project.write_text(project.read_text(encoding="utf-8") + "      - type: slack\n", "utf-8")
    missing = runner.invoke(app, ["check", "-c", str(project)])
    assert missing.exit_code == 1
    assert "✗ feedback/slack  sink slack: SLACK_WEBHOOK_URL is not set" in missing.stdout
    assert "fix: set it in" in missing.stdout
    assert "keys: https://docs.slack.dev/" in missing.stdout

    monkeypatch.setenv("SLACK_WEBHOOK_URL", HOOK)
    blocked = runner.invoke(app, ["check", "-c", str(project)])
    assert "✗ feedback/slack  sink slack: egress to 'hooks.slack.com' is blocked" in blocked.stdout

    monkeypatch.setenv("OBSEI_EGRESS_MODE", "hybrid")
    requested = _http(monkeypatch, _slack)
    verified = runner.invoke(app, ["check", "-c", str(project)])
    assert verified.exit_code == 0, verified.output
    assert "✓ feedback/slack  sink slack: credentials work" in verified.stdout
    assert [json.loads(r.content) for r in requested] == [{}]


def test_yaml_edits_keep_comments_and_layout() -> None:
    text = (
        "version: 1  # keep\n"
        "pipelines:\n"
        "  - name: a\n"
        "    sources: [{key: s, type: csv, config: {path: a.csv}}]\n"
        "    sinks:\n"
        "  - name: b  # second\n"
        "    sources:\n"
        "    - key: s\n"
        "      type: csv\n"
        "      config:\n"
        "        path: b.csv\n"
        "    # trailing comment\n"
        "plugins: []\n"
    )
    item: dict[str, JsonValue] = {
        "type": "parquet",
        "config": {"directory": "out", "tags": ["x", "y"]},
    }
    text = yamledit.append(text, yamledit.pipeline("a"), "sinks", item)
    text = yamledit.append(text, yamledit.pipeline("a"), "sources", {"key": "t", "type": "rss"})
    text = yamledit.append(text, yamledit.pipeline("b"), "sources", {"key": "t", "type": "rss"})
    text = yamledit.append(text, yamledit.pipeline("b"), "enrichers", {"type": "classify"})
    text = yamledit.append(text, yamledit.root, "plugins", "teams")
    text = yamledit.add_mapping(text, "egress", {"mode": "air_gapped"})
    text = yamledit.set_scalar(text, yamledit.child("egress"), "mode", "private")
    text = yamledit.append(text, yamledit.child("egress"), "allowed_hosts", "hooks.slack.com")
    assert all(c in text for c in ("# keep", "# second", "# trailing comment"))
    assert "    sinks:\n      - type: parquet\n        config:\n          directory: out\n" in text
    assert "          tags: [x, y]\n" in text
    assert "    - key: t\n      type: rss\n" in text
    data = yaml.safe_load(text)
    assert [p["name"] for p in data["pipelines"]] == ["a", "b"]
    assert [s["key"] for s in data["pipelines"][0]["sources"]] == ["s", "t"]
    assert data["pipelines"][1]["enrichers"] == [{"type": "classify"}]
    assert data["plugins"] == ["teams"]
    assert data["egress"] == {"mode": "private", "allowed_hosts": ["hooks.slack.com"]}
    with pytest.raises(yamledit.EditError, match="no pipeline named 'c'"):
        yamledit.append(text, yamledit.pipeline("c"), "sinks", item)


def test_save_secrets_replaces_only_its_names(tmp_path: Path) -> None:
    save_secrets(tmp_path, {"A": "1", "B": "2"})
    save_secrets(tmp_path, {"A": "3"})
    assert _secrets(tmp_path / "obsei.yaml") == {"B": "2", "A": "3"}


def test_the_packaged_plugin_template_matches_plugins_template() -> None:
    template = ROOT / "plugins" / "template"
    packaged = dict(cli._template(resources.files("obsei") / "templates" / "plugin"))
    expected = {
        p.relative_to(template).as_posix(): p.read_text(encoding="utf-8")
        for p in template.rglob("*")
        if p.is_file() and "__pycache__" not in p.parts and ".pytest_cache" not in p.parts
    }
    assert packaged == expected


def test_plugin_new_scaffolds_a_working_plugin(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "obsei-acme_feed"
    result = runner.invoke(app, ["plugin", "new", "acme_feed", "--dir", str(target)])
    assert result.exit_code == 0, result.output
    pyproject = (target / "pyproject.toml").read_text(encoding="utf-8")
    assert 'name = "obsei-acme-feed"' in pyproject
    assert 'acme_feed = "obsei_acme_feed:register"' in pyproject
    assert (target / "tests" / "test_acme_feed_plugin.py").is_file()
    monkeypatch.syspath_prepend(str(target / "src"))
    from obsei_acme_feed import register  # type: ignore[import-not-found]  # noqa: PLC0415

    registry = builtin_registry()
    register(registry)
    plugin = registry.source("acme_feed")
    assert plugin.catalog == Catalog(title="AcmeFeed", category="data", docs_url=TEMPLATE_DOCS)
    assert runner.invoke(app, ["plugin", "new", "acme_feed", "--dir", str(target)]).exit_code == 2
    assert runner.invoke(app, ["plugin", "new", "Acme"]).exit_code == 2


def test_add_never_leaves_a_broken_file(project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    before = project.read_text(encoding="utf-8")
    monkeypatch.setattr(yamledit, "append", lambda text, *args: text + "pipelines: oops\n")
    _http(monkeypatch, _feed)
    result = runner.invoke(
        app, ["add", "rss", "-c", str(project), "--yes", "--set", "url=https://x.io/feed"]
    )
    assert result.exit_code == 2
    assert "obsei.yaml was left unchanged" in result.output
    assert project.read_text(encoding="utf-8") == before
    assert parse_config(before)
