import json
import re
from pathlib import Path

import pytest
import yaml

from obsei._version import RELEASE_VERSION

ROOT = Path(__file__).resolve().parents[3]
PLUGIN = ROOT / "integrations/claude/obsei"
MARKETPLACES = [
    ROOT / ".claude-plugin/marketplace.json",
    ROOT / ".cursor-plugin/marketplace.json",
    ROOT / ".agents/plugins/marketplace.json",
]
MANIFESTS = [
    *MARKETPLACES,
    PLUGIN / ".claude-plugin/plugin.json",
    PLUGIN / ".cursor-plugin/plugin.json",
    PLUGIN / ".mcp.json",
    ROOT / "gemini-extension.json",
    ROOT / "server.json",
]
MCP_SERVER = {"command": "uvx", "args": ["--from", "obsei>=1.0.0rc1", "obsei", "mcp"]}


def load(path: Path) -> dict[str, object]:
    data: dict[str, object] = json.loads(path.read_text(encoding="utf-8"))
    return data


@pytest.mark.parametrize("path", MANIFESTS, ids=lambda p: str(p.relative_to(ROOT)))
def test_manifest_version_matches_release(path: Path) -> None:
    data = load(path)
    if "version" in data:
        assert data["version"] == RELEASE_VERSION


def test_every_config_runs_the_same_mcp_command() -> None:
    for path in (PLUGIN / ".mcp.json", ROOT / "gemini-extension.json"):
        assert load(path)["mcpServers"] == {"obsei": MCP_SERVER}, path
    server = json.loads((ROOT / "server.json").read_text(encoding="utf-8"))
    package = server["packages"][0]
    assert package["version"] == RELEASE_VERSION
    assert package["packageArguments"] == [{"type": "positional", "value": "mcp"}]
    readme = (ROOT / "packages/obsei/README.md").read_text(encoding="utf-8")
    assert f"mcp-name: {server['name']} " in readme


@pytest.mark.parametrize("path", MARKETPLACES, ids=lambda p: str(p.relative_to(ROOT)))
def test_marketplace_points_at_the_plugin(path: Path) -> None:
    source = json.loads(path.read_text(encoding="utf-8"))["plugins"][0]["source"]
    target = source["path"] if isinstance(source, dict) else source
    assert (ROOT / target).resolve() == PLUGIN


def test_gemini_context_file_exists() -> None:
    assert (ROOT / str(load(ROOT / "gemini-extension.json")["contextFileName"])).is_file()


def test_skills_follow_the_agent_skills_spec() -> None:
    skills = sorted((PLUGIN / "skills").glob("*/SKILL.md"))
    assert skills
    for skill in skills:
        text = skill.read_text(encoding="utf-8")
        front = yaml.safe_load(text.split("---")[1])
        assert front["name"] == skill.parent.name
        assert re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", front["name"])
        assert 0 < len(front["description"]) <= 1024
        assert "claude" not in text.lower()
