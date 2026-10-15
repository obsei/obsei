# Integrations

| Integration | Path | How to use |
| --- | --- | --- |
| Claude Code plugin (MCP server and `voice-of-customer` skill) | [`claude/obsei`](claude/obsei), listed in [`../.claude-plugin/marketplace.json`](../.claude-plugin/marketplace.json) | `/plugin marketplace add obsei/obsei`, then `/plugin install obsei@obsei` |
| Codex, Copilot CLI, VS Code, Cursor, Gemini CLI plugins (same plugin folder and skill) | [`claude/obsei`](claude/obsei), [`../.agents/plugins`](../.agents/plugins), [`../.cursor-plugin`](../.cursor-plugin), [`../gemini-extension.json`](../gemini-extension.json) | [Use obsei from your AI tool](https://docs.obsei.com/guides/ai-tools/) |
| Any MCP client over stdio (Claude Desktop, Cline, Zed, JetBrains, Goose, your agents) | `obsei mcp`, published to the MCP Registry on release as `io.github.obsei/obsei` ([`../server.json`](../server.json)) | command: `uvx --from 'obsei>=1.0.0rc1' obsei mcp` (config below) |
| Remote MCP over HTTP | `obsei serve` | `https://your-host:8765/mcp` with `Authorization: Bearer <token>` (analyst role), or behind your SSO proxy |
| GitHub Action | [`../action.yml`](../action.yml) | `uses: obsei/obsei@<tag or SHA>`; daily recipe in [`../examples/github-actions`](../examples/github-actions) |
| Slack `/obsei` command | `obsei serve` | slash command URL `https://your-host/slack/commands`, `SLACK_SIGNING_SECRET` set, `hooks.slack.com` allowed by the egress policy |
| Slack, Jira, Linear, GitHub issues, webhooks, Parquet, SQL | built-in sinks | `sinks:` in `obsei.yaml`; see [`../examples`](../examples) |
| Docker | [`../Dockerfile`](../Dockerfile), `ghcr.io/obsei/obsei` | `docker run --rm -v "$PWD:/data" -w /data ghcr.io/obsei/obsei:<version> run` (entrypoint is `obsei`) |
| Plugins (sources, enrichers, sinks) | [`../plugins`](../plugins): [`template`](../plugins/template), [`obsei-reddit`](../plugins/obsei-reddit) | install the package, then allow it by entry-point name: `plugins: [reddit]` |

The MCP tools `search_feedback`, `feedback_stats`, `get_feedback` and `list_themes` are read-only.
They return redacted text and labels with record ids for citation, never author pseudonyms.
`propose_issue` only queues an issue for a person to approve (`obsei approvals`).

Claude Desktop (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "obsei": {
      "command": "uvx",
      "args": ["--from", "obsei>=1.0.0rc1", "obsei", "mcp"],
      "env": { "OBSEI_DB": "/path/to/obsei.duckdb", "OBSEI_DB_KEY": "..." }
    }
  }
}
```
