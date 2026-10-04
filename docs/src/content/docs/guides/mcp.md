---
title: MCP and agents
description: Let Claude, ChatGPT, Cursor and your own agents query feedback.
sidebar:
  order: 5
---

`obsei mcp` (install `obsei[mcp]`) serves four read-only tools over stdio:

| Tool | Use |
| --- | --- |
| `feedback_stats` | Counts and average rating grouped by source, instance, sentiment, intent, language, rating, day, week or month |
| `search_feedback` | Matching feedback, newest first, as citable evidence |
| `get_feedback` | One record by id, to verify a citation |
| `list_themes` | Stable themes with trends, sources, languages and intents (k-anonymous) |

Results contain redacted text, labels, source, time and record id. They never contain author
pseudonyms. The server also offers a `voc_report` prompt.

## Claude Code

```bash
/plugin marketplace add obsei/obsei
/plugin install obsei@obsei
```

The plugin adds the MCP server and a `voice-of-customer` skill.

## Claude Desktop, Cursor, VS Code and others

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

## Remote MCP

`obsei serve` exposes the same tools at `/mcp` (streamable HTTP). Set `OBSEI_API_TOKEN`; clients
send `Authorization: Bearer <token>`. Put it behind your SSO proxy for per-user access.
