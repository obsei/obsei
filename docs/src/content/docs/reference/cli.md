---
title: CLI
description: obsei command reference.
---

| Command | Purpose |
| --- | --- |
| `obsei init [DIR] [--force] [--offline]` | Create `obsei.yaml`, a sample dataset and `.obsei/secrets.env` (a random `OBSEI_DB_KEY` and `OBSEI_PSEUDONYM_SALT`, owner-only, added to `.gitignore`, never overwritten), and install DuckDB's `httpfs` extension for encryption and, with `obsei[local]`, the classifier model, enabling the `classify` enricher (`--offline` skips the downloads; `--force` replaces only `obsei.yaml` and `feedback.csv`) |
| `obsei integrations [QUERY] [--category C] [--json]` | List every source, enricher and sink, built in or from an installed plugin, with its status, the secrets it needs and where to get them ([Setup](/guides/setup/#find-an-integration)) |
| `obsei add TYPE\|alert [-c FILE] [-p NAME] [--key KEY] [--as source\|sink] [--set FIELD=VALUE ...] [--all] [--yes]` | Add a source, sink or alert to `obsei.yaml`: asks for its settings, stores secrets in `.obsei/secrets.env`, previews a source or checks a sink, allows the sink's host in `egress:` with consent, and keeps comments; `--yes` asks nothing ([Setup](/guides/setup/#add-a-source-or-sink)) |
| `obsei check [-c FILE] [-p NAME]` | Build every source, sink and alert target, fetch one record per source and check sink credentials where that sends nothing; exits 1 if any failed |
| `obsei try [LINK\|FILE] [-c FILE] [-p NAME] [--limit N] [--no-enrich] [--json]` | Preview up to N (default 10) records per source as a table of redacted text and labels, with a redaction summary; from the configured sources, or an App Store, GitHub, Hacker News or RSS/Atom link or a `.csv`/`.jsonl`/`.json` file (see [Quickstart](/quickstart/#preview-with-obsei-try)). Nothing stored or sent; `--json` prints JSON Lines |
| `obsei run [-c FILE] [-p NAME] [--db PATH] [--every MINUTES]` | Run pipelines, then check alerts |
| `obsei themes [-c FILE] [--db PATH]` | Embed new feedback, update stable themes, then check alerts |
| `obsei alerts check [-c FILE] [--db PATH] [--dry-run]` | Check every [alert](/guides/alerts/) now and deliver those due (`--dry-run`: print only, send and record nothing) |
| `obsei alerts list [-c FILE] [--db PATH]` | Show when each alert key last fired, and snoozes and acks |
| `obsei alerts snooze ALERT KEY [--hours N] [-c FILE] [--db PATH]` | Silence one alert key for N hours (default 24) |
| `obsei alerts ack ALERT KEY [--by NAME] [-c FILE] [--db PATH]` | Acknowledge one alert key: silent for 7 days |
| `obsei ask QUESTION [-c FILE] [--db PATH]` | Answer from your feedback with citations; with `ask_judge`, also a grounding score |
| `obsei eval GOLD.csv \| --demo \| --from-store [-c FILE] [-p NAME] [--db PATH] [--json] [--target-precision P] [--min-accuracy A]` | Measure the `classify` enricher on labelled feedback and suggest a cutoff per question; exits 1 only when `--min-accuracy` is not met ([Models](/guides/models/#measure-on-your-own-data)) |
| `obsei correct FILE.csv [-c FILE] [-p NAME] [--db PATH]` | Store human labels (`id` and a column per question) in place of the model's answers |
| `obsei reprocess [-c FILE] [-p NAME] [--db PATH] [--since DATE] [--dry-run]` | Relabel stored records with the current `classify` config, keeping human labels, and report what changed |
| `obsei studio --out DIR [-c FILE] [--db PATH]` | Export a static Studio snapshot |
| `obsei demo [--out DIR] [--embedder hashing\|local\|local:MODEL] [--local-labels \| --decision-url-env VAR [--decision-model NAME]] [--save-labels FILE]` | Build the synthetic multilingual demo (default: offline `hashing` embedder and the committed labels from the local classifier) |
| `obsei models download [--embeddings MODEL] [--classifier MODEL ...] [--dir DIR]` | Fetch the local embedding model (`obsei[embeddings]`) and classifier models (`obsei[local]`) for offline use; by default, those of the installed extras |
| `obsei mcp [-c FILE] [--db PATH]` | MCP server over stdio (read-only, except to queue a proposal) |
| `obsei approvals list [--status pending\|approved\|rejected\|failed] [-c FILE] [--db PATH] [--unencrypted]` | List what agents proposed, newest first |
| `obsei approvals show ID [-c FILE] [--db PATH] [--unencrypted]` | Show a proposal and the exact issue text approving it sends |
| `obsei approvals approve ID [--by NAME] [-c FILE] [--db PATH]` | Open the proposed issue with the configured sink, once (a failed one can be approved again) |
| `obsei approvals reject ID [--by NAME] [--reason TEXT] [-c FILE] [--db PATH] [--unencrypted]` | Reject a proposal; nothing is sent |
| `obsei serve [-c FILE] [--db PATH] [--host] [--port]` | Scheduled pipelines, webhook intake, MCP over HTTP, Studio (see [Server](/guides/serve/)) |
| `obsei export --author HANDLE [--out FILE] [-c FILE] [--db PATH] [--unencrypted]` | Export one author's records |
| `obsei forget --author / --source [--instance] / --older-than-days [-c FILE] [--db PATH] [--unencrypted]` | Erase records (tombstoned so they are never stored again) |
| `obsei audit [--limit N] [-c FILE] [--db PATH] [--unencrypted]` | Show the erasure, export, access and approval log |
| `obsei doctor [-c FILE]` | Check environment, where the secrets came from, encryption, egress mode and plugins |
| `obsei schema [record\|config]` | Print the Feedback Record JSON Schema, or `obsei.yaml`'s with the config of every installed integration ([editor autocomplete](/guides/setup/#editor-autocomplete)) |
| `obsei plugin new NAME [--dir DIR]` | Create a plugin package from the template ([Plugins](/reference/plugins/#writing-a-plugin)) |
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
