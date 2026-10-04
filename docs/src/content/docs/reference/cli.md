---
title: CLI
description: obsei command reference.
---

| Command | Purpose |
| --- | --- |
| `obsei init [DIR] [--force] [--offline]` | Create `obsei.yaml` and a sample dataset, and install DuckDB's `httpfs` extension for encryption (`--offline` skips it; existing files are kept, so rerun it to install the extension) |
| `obsei try [-c FILE] [-p NAME] [--limit N] [--enrich]` | Preview redacted records; nothing stored or sent |
| `obsei run [-c FILE] [-p NAME] [--db PATH] [--every MINUTES]` | Run pipelines |
| `obsei themes [-c FILE] [--db PATH]` | Embed new feedback and update stable themes |
| `obsei ask QUESTION [-c FILE] [--db PATH]` | Answer from your feedback with citations; with `ask_judge`, also a grounding score |
| `obsei studio --out DIR [-c FILE] [--db PATH]` | Export a static Studio snapshot |
| `obsei demo [--out DIR] [--embedder hashing\|local\|local:MODEL] [--decision-url-env VAR [--decision-model NAME] [--save-labels FILE]]` | Build the synthetic multilingual demo (default: offline `hashing` embedder and the committed decision-model labels) |
| `obsei models download [--embeddings MODEL] [--dir DIR]` | Fetch the local multilingual embedding model for offline use |
| `obsei mcp [-c FILE] [--db PATH]` | MCP server over stdio (read-only) |
| `obsei serve [-c FILE] [--db PATH] [--host] [--port]` | Scheduled pipelines, webhook intake, MCP over HTTP, Studio (see [Server](/guides/serve/)) |
| `obsei export --author HANDLE [--out FILE] [-c FILE] [--db PATH] [--unencrypted]` | Export one author's records |
| `obsei forget --author / --source [--instance] / --older-than-days [-c FILE] [--db PATH] [--unencrypted]` | Erase records (tombstoned so they are never stored again) |
| `obsei audit [--limit N] [-c FILE] [--db PATH] [--unencrypted]` | Show the erasure, export and access log |
| `obsei doctor` | Check environment, encryption, egress mode and plugins |
| `obsei schema` | Print the Feedback Record JSON Schema |
| `obsei version` (or `--version`) | Print the version |

`-c/--config` defaults to `obsei.yaml` (`OBSEI_CONFIG`). `--db` overrides the database path
(`OBSEI_DB`); otherwise commands that read the config use `store.path`. `--unencrypted` opens a
database without `OBSEI_DB_KEY` (encrypted disks only); commands that read the config use
`store.unencrypted: true` instead.

## Environment

| Variable | Purpose |
| --- | --- |
| `OBSEI_CONFIG` | Path to `obsei.yaml` |
| `OBSEI_DB` | Database path override |
| `OBSEI_DB_KEY` | Database encryption key (16+ characters) |
| `OBSEI_DUCKDB_EXTENSIONS` | Directory with pre-installed DuckDB extensions (`httpfs`) |
| `OBSEI_PSEUDONYM_SALT` | Author pseudonym salt (16+ characters) |
| `OBSEI_EGRESS_MODE`, `OBSEI_EGRESS_ALLOW` | Egress policy |
| `OBSEI_MODELS_DIR` | Directory for local models (`obsei models download --dir`); air-gapped runs load them from here |
| `OBSEI_API_TOKEN` | Admin bearer token for `obsei serve` |
| `SLACK_SIGNING_SECRET` | Enables the `/obsei` Slack command |
