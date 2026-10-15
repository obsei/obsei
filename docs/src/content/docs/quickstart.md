---
title: Quickstart
description: Install obsei, create a project and run your first pipeline.
---

Five minutes, no model server and no secrets to export:

```bash
mkdir voc && cd voc
uvx --from "obsei[recommended]>=1.0" obsei init   # project, secrets, sample data, local model
obsei try                                        # redacted, labelled preview of the sample
obsei try https://apps.apple.com/us/app/whatsapp-messenger/id310633997   # any public link
obsei run                                        # fetch, redact, label, deliver, store
```

Then add your own sources and sinks without editing YAML: `obsei add appstore`, `obsei add slack`,
`obsei check` (see [Set up without editing YAML](/guides/setup/)).

`obsei[recommended]` is the full local setup: the classifier (`local`) and multilingual themes
(`embeddings`). `uvx` runs obsei without installing it; to keep the `obsei` command, install it
once with `uv tool install "obsei[recommended]"` (or `pip install`).

`obsei init` creates:

- `obsei.yaml`, with the `classify` enricher on when `obsei[local]` is installed, and
  `feedback.csv`, a sample in ten languages with a few synthetic emails, phone numbers and card
  numbers so you can see redaction work.
- `.obsei/secrets.env` with a random database key (`OBSEI_DB_KEY`) and author pseudonym salt
  (`OBSEI_PSEUDONYM_SALT`), readable only by you, and `.obsei/` in `.gitignore`. Every command
  loads it; variables already set in the environment win, and `obsei doctor` shows where each came
  from. Back the file up: without the key the database cannot be read, and a new salt produces new
  pseudonyms. `obsei init` never overwrites it.
- DuckDB's `httpfs` extension for encryption and, with `obsei[local]`, the classifier model
  (about 2.2 GB, once). `--offline` skips both downloads.

On servers and in CI, set `OBSEI_DB_KEY` and `OBSEI_PSEUDONYM_SALT` from your secret manager, or
mount a `.obsei/secrets.env` next to `obsei.yaml`.

## Preview with `obsei try`

`obsei try` prints a table of up to 10 records per source (`--limit`): source, language, labels
with the model's confidence (`review` marks answers below the cutoff) and the redacted text. Below
it, the number of values redacted per type and before and after for three records. Nothing is
stored or sent; the original text exists only in that preview. `--json` prints one JSON object per
record instead, and `--no-enrich` skips the classifier. If the classifier cannot run, the table
still shows redaction and a warning says why.

Without an argument it reads the sources in `obsei.yaml`. With a link or a file it reads only that,
with redaction always on and the enrichers of the first pipeline (or `-p NAME`); outside a project,
with the local classifier when `obsei[local]` is installed:

| Argument | Source |
| --- | --- |
| `https://apps.apple.com/<country>/app/<name>/id<digits>` | `appstore`, that app and country |
| `https://github.com/<owner>/<repo>` | `github_issues`, without a token |
| `https://news.ycombinator.com/item?id=<id>` or an `hn.algolia.com` search | `hackernews` |
| `https://wordpress.org/support/plugin/<slug>/reviews/` | `rss`, the plugin's review feed |
| Any other link | `rss` (RSS 2.0 or Atom) |
| `.csv`, `.jsonl`, `.json` file | `csv`, `jsonl` or `filedrop`, text from a `text`, `comment`, `review`, `body`, `content`, `message` or `feedback` column |

Google Play, YouTube and Bluesky need credentials, so `obsei try` names the source to configure
instead. The preview fetches only from the link's host. The egress policy governs where feedback
is sent (models and sinks), and the local classifier runs in process, so nothing else is
contacted.

:::caution[If `obsei run` says "writing an encrypted store needs DuckDB's httpfs extension"]
Encryption uses DuckDB's `httpfs` extension, and the default air-gapped mode never downloads it.
`obsei init` installs it, except with `--offline`. Otherwise install it once yourself; this
fetches DuckDB's own extension and sends none of your data:

```bash
"$(uv tool dir)/obsei/bin/python" -c "import duckdb; duckdb.connect().execute('INSTALL httpfs')"
# installed with pip: run python -c "..." with the same command, in the environment that has obsei
```

Then `obsei doctor` reports `encryption: ready`. For machines without network access, see [At rest and in use](/privacy/overview/#at-rest-and-in-use).
:::

## Optional extras

Some features need extra packages. Add them to the same install:

| Extra | Adds |
| --- | --- |
| `recommended` | `local` and `embeddings`: everything that runs on this machine |
| `mcp` | `obsei serve`, `obsei mcp` and Studio over HTTP |
| `local` | the local classifier for `classify` (PyTorch; no model server) |
| `embeddings` | the local multilingual model, so themes group across languages |
| `names` | local name redaction (GLiNER) |
| `sql` | the SQL source and sink |
| `google` | the Google Play source |
| `apple` | the App Store Connect source |

```bash
# uv tool: --force replaces the install, so list every extra you want to keep
uv tool install --force "obsei[mcp,embeddings]"
# pip, in the environment where obsei is installed
pip install "obsei[mcp,embeddings]"
```

`uv run --extra ...` only works inside a project checkout; outside one it ignores the extra.
Plugins install the same way: `uv tool install --force obsei --with obsei-teams`
(see [Plugins](/reference/plugins/)).

## Add a model

The default classifier runs inside obsei on the CPU, so there is no model server to start. If you
ran `obsei init` without `obsei[local]`, add it and fetch the model:

```bash
uv tool install --force "obsei[local]"   # or: pip install "obsei[local]"
obsei models download                   # once, with network (about 2.2 GB)
```

Then uncomment the `classify` enricher in `obsei.yaml`. Every record gets sentiment, intent and
language, with a probability for each answer; answers below the cutoff are marked for review. To
use a decision model, Ollama or a hosted LLM instead, or to add the chat model that `obsei ask`
needs, see [Models](/guides/models/).

## Ask your agent

```bash
claude mcp add obsei -- obsei mcp
```

Then ask: *"What are the top complaints this month, by country?"* See
[MCP and agents](/guides/mcp/).

## Run with Docker

Run inside the project directory. The image's entrypoint is `obsei`, so arguments are subcommands:

<!-- x-release-please-start-version -->
```bash
docker run --rm -v "$PWD:/data" -w /data --user "$(id -u):$(id -g)" \
  ghcr.io/obsei/obsei:1.0.0 run
```

The container reads `.obsei/secrets.env` from the mounted project; pass `-e OBSEI_DB_KEY -e
OBSEI_PSEUDONYM_SALT` instead when the secrets come from the environment.

Images are tagged by release (`1.0.0`); there is no `latest` tag yet. `--user` keeps the
database and outputs owned by you.
<!-- x-release-please-end -->

## Docker Compose

[`docker-compose.yml`](https://github.com/obsei/obsei/blob/master/docker-compose.yml) runs
`obsei serve` with the store in a named volume and your `obsei.yaml` mounted read-only. Copy it and
[`.env.example`](https://github.com/obsei/obsei/blob/master/.env.example) into your project
directory:

```bash
cp .env.example .env    # fill in OBSEI_DB_KEY, OBSEI_PSEUDONYM_SALT (e.g. from .obsei/secrets.env) and OBSEI_API_TOKEN
docker compose up -d
docker compose ps       # healthy once /healthz answers
```

Studio is at `http://localhost:8765/studio/` and MCP at `http://localhost:8765/mcp`, both behind
`OBSEI_API_TOKEN` (see [Server and webhooks](/guides/serve/)). The port is published on
`127.0.0.1` only; change the mapping to expose it. Files your pipelines read, such as a CSV,
need their own mount under `/data`.
