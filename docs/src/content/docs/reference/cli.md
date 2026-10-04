---
title: CLI
description: obsei command reference.
---

| Command | Purpose |
| --- | --- |
| `obsei init [DIR]` | Create `obsei.yaml` and a sample dataset |
| `obsei try [-p NAME] [--limit N] [--enrich]` | Preview redacted records; nothing stored or sent |
| `obsei run [-p NAME] [--every MINUTES]` | Run pipelines |
| `obsei themes` | Embed new feedback and update stable themes |
| `obsei ask QUESTION` | Answer from your feedback with citations |
| `obsei studio --out DIR` | Export a static Studio snapshot |
| `obsei demo [--out DIR]` | Build the synthetic multilingual demo |
| `obsei mcp` | MCP server over stdio (read-only) |
| `obsei serve [--host] [--port]` | Webhook intake, MCP over HTTP, `/healthz` |
| `obsei export --author HANDLE [--out FILE]` | Export one author's records |
| `obsei forget --author / --source / --older-than-days` | Erase records |
| `obsei audit` | Show the erasure and export log |
| `obsei doctor` | Check environment, encryption, egress mode and plugins |
| `obsei schema` | Print the Feedback Record JSON Schema |

## Environment

| Variable | Purpose |
| --- | --- |
| `OBSEI_CONFIG` | Path to `obsei.yaml` |
| `OBSEI_DB` | Database path override |
| `OBSEI_DB_KEY` | Database encryption key (16+ characters) |
| `OBSEI_PSEUDONYM_SALT` | Author pseudonym salt (16+ characters) |
| `OBSEI_EGRESS_MODE`, `OBSEI_EGRESS_ALLOW` | Egress policy |
| `OBSEI_API_TOKEN` | Bearer token for `obsei serve` |
| `SLACK_SIGNING_SECRET` | Enables the `/obsei` Slack command |
