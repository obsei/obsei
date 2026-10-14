---
title: Quickstart
description: Install obsei, create a project and run your first pipeline.
---

obsei 1.0 is in pre-release. Install it with an explicit version specifier, which keeps
dependencies on stable releases:

```bash
uv tool install "obsei[mcp]>=1.0.0rc1"     # or: pip install "obsei[mcp]>=1.0.0rc1"
```

Create a project with a ten-language sample dataset:

```bash
mkdir voc && cd voc
obsei init
export OBSEI_DB_KEY="$(openssl rand -hex 24)"          # encrypts the database
export OBSEI_PSEUDONYM_SALT="$(openssl rand -hex 24)"  # pseudonymises authors
obsei try      # preview redacted records; nothing stored or sent
obsei run      # fetch, redact, enrich, deliver, store
```

Keep both secrets in your secret manager: without the key the database cannot be read, and a new
salt produces new pseudonyms.

:::caution[If `obsei run` says "writing an encrypted store needs DuckDB's httpfs extension"]
Encryption uses DuckDB's `httpfs` extension, and the default air-gapped mode never downloads it.
Up to 1.0.0rc2, install it once yourself; this fetches DuckDB's own extension and sends none of
your data:

```bash
"$(uv tool dir)/obsei/bin/python" -c "import duckdb; duckdb.connect().execute('INSTALL httpfs')"
# installed with pip: run python -c "..." with the same command, in the environment that has obsei
```

Then `obsei doctor` reports `encryption: ready`. From 1.0.0rc3, `obsei init` installs it for you.
For machines without network access, see [At rest and in use](/privacy/overview/#at-rest-and-in-use).
:::

## Optional extras

Some features need extra packages. Add them to the same install:

| Extra | Adds |
| --- | --- |
| `mcp` | `obsei serve`, `obsei mcp` and Studio over HTTP |
| `local` | the local classifier for `classify` (PyTorch; no model server) |
| `embeddings` | the local multilingual model, so themes group across languages |
| `names` | local name redaction (GLiNER) |
| `sql` | the SQL source and sink |
| `google` | the Google Play source |
| `apple` | the App Store Connect source |

```bash
# uv tool: --force replaces the install, so list every extra you want to keep
uv tool install --force "obsei[mcp,embeddings]>=1.0.0rc1"
# pip, in the environment where obsei is installed
pip install "obsei[mcp,embeddings]>=1.0.0rc1"
```

`uv run --extra ...` only works inside a project checkout; outside one it ignores the extra.
Plugins install the same way: `uv tool install --force "obsei[mcp]>=1.0.0rc1" --with obsei-teams`
(see [Plugins](/reference/plugins/)).

## Add a model

The default classifier runs inside obsei on the CPU, so there is no model server to start:

```bash
uv tool install --force "obsei[mcp,local]>=1.0.0rc1"   # or: pip install "obsei[local]>=1.0.0rc1"
obsei models download                                 # once, with network (about 2.2 GB)
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
  -e OBSEI_DB_KEY -e OBSEI_PSEUDONYM_SALT \
  ghcr.io/obsei/obsei:1.0.0-rc.4 run
```

Images are tagged by release (`1.0.0-rc.4`); there is no `latest` tag yet. `--user` keeps the
database and outputs owned by you.
<!-- x-release-please-end -->

## Docker Compose

[`docker-compose.yml`](https://github.com/obsei/obsei/blob/master/docker-compose.yml) runs
`obsei serve` with the store in a named volume and your `obsei.yaml` mounted read-only. Copy it and
[`.env.example`](https://github.com/obsei/obsei/blob/master/.env.example) into your project
directory:

```bash
cp .env.example .env    # fill in OBSEI_DB_KEY, OBSEI_PSEUDONYM_SALT and OBSEI_API_TOKEN
docker compose up -d
docker compose ps       # healthy once /healthz answers
```

Studio is at `http://localhost:8765/studio/` and MCP at `http://localhost:8765/mcp`, both behind
`OBSEI_API_TOKEN` (see [Server and webhooks](/guides/serve/)). The port is published on
`127.0.0.1` only; change the mapping to expose it. Files your pipelines read, such as a CSV,
need their own mount under `/data`.
