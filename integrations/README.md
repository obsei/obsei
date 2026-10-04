# Integrations

| Integration | Path | How to use |
| --- | --- | --- |
| Claude Code plugin | [`claude/obsei`](claude/obsei) | `/plugin marketplace add obsei/obsei`, then `/plugin install obsei@obsei` |
| Any MCP client (Claude Desktop, ChatGPT, Cursor, VS Code, your agents) | `obsei mcp` | stdio command: `uvx --from 'obsei[mcp]>=1.0.0a1' obsei mcp` |
| Remote MCP over HTTP | `obsei serve` | `https://your-host:8765/mcp` with `Authorization: Bearer $OBSEI_API_TOKEN` |
| GitHub Action | [`../action.yml`](../action.yml) | see [`../examples/github-actions`](../examples/github-actions) |

The MCP tools are read-only: `search_feedback`, `feedback_stats`, `get_feedback` and `list_themes`.
They return redacted text and labels with record ids for citation, never author pseudonyms.

Claude Desktop (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "obsei": {
      "command": "uvx",
      "args": ["--from", "obsei[mcp]>=1.0.0a1", "obsei", "mcp"],
      "env": { "OBSEI_DB": "/path/to/obsei.duckdb", "OBSEI_DB_KEY": "..." }
    }
  }
}
```
