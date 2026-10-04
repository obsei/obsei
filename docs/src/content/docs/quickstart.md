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

## Add a model

Start [Ollama](https://ollama.com) with a model such as `qwen3:8b`, then uncomment the
`classify` enricher in `obsei.yaml`. Every record gets sentiment, intent, language and a
confidence score. If the model cannot be reached, `obsei run` warns with the endpoint, stores
the records unlabelled and labels them on the next run. See [Models](/guides/models/) for hosted
and enterprise endpoints.

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
  ghcr.io/obsei/obsei:1.0.0-rc.3 run
```

Images are tagged by release (`1.0.0-rc.3`); there is no `latest` tag yet. `--user` keeps the
database and outputs owned by you.
<!-- x-release-please-end -->
