---
title: Quickstart
description: Install obsei, create a project and run your first pipeline.
---

obsei 1.0 is in pre-release. Install it with pre-releases allowed:

```bash
uv tool install --prerelease allow "obsei[mcp]"     # or: pip install --pre "obsei[mcp]"
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

```bash
docker run --rm -v "$PWD:/home/obsei" -e OBSEI_DB_KEY -e OBSEI_PSEUDONYM_SALT \
  ghcr.io/obsei/obsei run
```
