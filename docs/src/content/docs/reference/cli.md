---
title: CLI
description: obsei command reference.
---

| Command | Purpose |
| --- | --- |
| `obsei init [DIR] [--force] [--offline]` | Create `obsei.yaml`, a sample dataset and `.obsei/secrets.env` (a random `OBSEI_DB_KEY` and `OBSEI_PSEUDONYM_SALT`, owner-only, added to `.gitignore`, never overwritten), and install DuckDB's `httpfs` extension for encryption and, with `obsei[local]`, the classifier model, enabling the `classify` enricher (`--offline` skips the downloads; `--force` replaces only `obsei.yaml` and `feedback.csv`) |
| `obsei try [LINK\|FILE] [-c FILE] [-p NAME] [--limit N] [--no-enrich] [--json]` | Preview up to N (default 10) records per source as a table of redacted text and labels, with a redaction summary; from the configured sources, or an App Store, GitHub, Hacker News or RSS/Atom link or a `.csv`/`.jsonl`/`.json` file (see [Quickstart](/quickstart/#preview-with-obsei-try)). Nothing stored or sent; `--json` prints JSON Lines |
| `obsei run [-c FILE] [-p NAME] [--db PATH] [--every MINUTES]` | Run pipelines, then check alerts |
| `obsei themes [-c FILE] [--db PATH]` | Embed new feedback, update stable themes, then check alerts |
| `obsei alerts check [-c FILE] [--db PATH] [--dry-run]` | Check every [alert](/guides/alerts/) now and deliver those due (`--dry-run`: print only, send and record nothing) |
| `obsei alerts list [-c FILE] [--db PATH]` | Show when each alert key last fired, and snoozes and acks |
| `obsei alerts snooze ALERT KEY [--hours N] [-c FILE] [--db PATH]` | Silence one alert key for N hours (default 24) |
| `obsei alerts ack ALERT KEY [--by NAME] [-c FILE] [--db PATH]` | Acknowledge one alert key: silent for 7 days |
| `obsei ask QUESTION [-c FILE] [--db PATH]` | Answer from your feedback with citations; with `ask_judge`, also a grounding score |
| `obsei studio --out DIR [-c FILE] [--db PATH]` | Export a static Studio snapshot |
| `obsei demo [--out DIR] [--embedder hashing\|local\|local:MODEL] [--decision-url-env VAR [--decision-model NAME] [--save-labels FILE]]` | Build the synthetic multilingual demo (default: offline `hashing` embedder and the committed decision-model labels) |
| `obsei models download [--embeddings MODEL] [--classifier MODEL ...] [--dir DIR]` | Fetch the local embedding model (`obsei[embeddings]`) and classifier models (`obsei[local]`) for offline use; by default, those of the installed extras |
| `obsei mcp [-c FILE] [--db PATH]` | MCP server over stdio (read-only) |
| `obsei serve [-c FILE] [--db PATH] [--host] [--port]` | Scheduled pipelines, webhook intake, MCP over HTTP, Studio (see [Server](/guides/serve/)) |
| `obsei export --author HANDLE [--out FILE] [-c FILE] [--db PATH] [--unencrypted]` | Export one author's records |
| `obsei forget --author / --source [--instance] / --older-than-days [-c FILE] [--db PATH] [--unencrypted]` | Erase records (tombstoned so they are never stored again) |
| `obsei audit [--limit N] [-c FILE] [--db PATH] [--unencrypted]` | Show the erasure, export and access log |
| `obsei doctor [-c FILE]` | Check environment, where the secrets came from, encryption, egress mode and plugins |
| `obsei schema` | Print the Feedback Record JSON Schema |
| `obsei version` (or `--version`) | Print the version |

`-c/--config` defaults to `obsei.yaml` (`OBSEI_CONFIG`). `--db` overrides the database path
(`OBSEI_DB`); otherwise commands that read the config use `store.path`. `--unencrypted` opens a
database without `OBSEI_DB_KEY` (encrypted disks only); commands that read the config use
`store.unencrypted: true` instead.

Every command loads `.obsei/secrets.env` next to the config (`KEY=value` lines) and sets the
variables the environment does not already set. A wrong `OBSEI_DB_KEY` fails with "wrong encryption
key"; a salt shorter than 16 bytes fails before anything is fetched.

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
