---
title: MCP and agents
description: Let Claude, ChatGPT, Cursor and your own agents query feedback.
sidebar:
  order: 6
---

`obsei mcp` serves these tools over stdio:

| Tool | Use |
| --- | --- |
| `feedback_stats` | Counts and average rating grouped by source, instance, sentiment, intent, lang (language), rating, route, day, week or month |
| `search_feedback` | Matching feedback, newest first, as citable evidence |
| `get_feedback` | One record by id, to verify a citation |
| `list_themes` | Stable themes with trends (`rising` as Studio shows it), sources, languages and intents (k-anonymous) |
| `propose_issue` | Queue an issue for a person to approve (only when a GitHub, Jira or Linear sink is configured) |

Results contain redacted text, labels, source, time and record id. They never contain author
pseudonyms. The server also offers a `voc_report` prompt. Its `initialize` handshake negotiates
MCP protocol 2024-11-05 to 2025-11-25 (a client offering 2026-07-28 gets 2025-11-25); the
bundled MCP SDK also answers 2026-07-28 requests that carry their version in `_meta`. Every tool
declares `readOnlyHint`, `destructiveHint` and `openWorldHint`: the four read tools are
read-only, and `propose_issue` writes only to obsei's own queue.

## Untrusted text

Each evidence item's `text` is what a customer wrote, and anyone can write a review. Items carry
`"untrusted": true`, and the tool descriptions and server instructions tell agents to quote that
text and never follow instructions in it. Theme labels and descriptions are written by a model
from that text, so treat them the same way.

## Approvals

An agent cannot act outside obsei. `propose_issue(target, title, body, record_ids)` stores a
pending approval and returns its id; nothing is sent. `target` is the key of a `github_issues`,
`jira` or `linear` sink in `obsei.yaml` (the tool description lists them; a key that names
different sinks in several pipelines becomes `pipeline/key`). Cited record ids must exist.

A person then decides, with the CLI or, as admin, over HTTP:

```bash
obsei approvals list --status pending
obsei approvals show apr_...            # the proposal and the exact issue text
obsei approvals approve apr_... --by ana
obsei approvals reject apr_... --by ana --reason "duplicate of #12"
```

Approving opens the issue with that sink's settings. The issue starts with "Proposed by an AI
agent via obsei; review before acting" and lists the cited records. An approval is carried out
once: approving it again is refused, and if opening the issue failed you can approve it again
without risking a second issue, because the sink first looks for one tagged with the approval
id. Every proposal and decision is written to the audit log.

Over stdio, `obsei mcp` opens the store read-only, and read-write only for the moment it stores
a proposal. DuckDB allows one writer, so while `obsei serve` or `obsei run` holds the store,
send proposals through `obsei serve`'s `/mcp` instead.

The rule behind this: fixed labels from a classifier may pick routes on their own, but any free
text an agent writes after reading feedback goes through a person, because private data,
untrusted content and a way to send messages out together are what a prompt injection needs.

## Claude Code

```bash
/plugin marketplace add obsei/obsei
/plugin install obsei@obsei
```

The plugin adds the MCP server and a `voice-of-customer` skill. Codex, Copilot, VS Code, Cursor,
Gemini and other tools: see [Use obsei from your AI tool](/guides/ai-tools/).

## Claude Desktop and other clients

```json
{
  "mcpServers": {
    "obsei": {
      "command": "uvx",
      "args": ["--from", "obsei>=1.0", "obsei", "mcp"],
      "env": { "OBSEI_DB": "/path/to/obsei.duckdb", "OBSEI_DB_KEY": "..." }
    }
  }
}
```

## Remote MCP

`obsei serve` exposes the same tools at `/mcp` (streamable HTTP). Set `OBSEI_API_TOKEN`; clients
send `Authorization: Bearer <token>`. Put it behind your SSO proxy for per-user access. Give
agents an analyst token: proposals then record who made them (`agent:<user>`), and only admins
can approve them.
