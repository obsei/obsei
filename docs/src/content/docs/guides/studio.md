---
title: Studio
description: The read-only web UI with a knowledge-graph explorer.
sidebar:
  order: 8
---

[Open the demo](/demo/) (synthetic feedback in eight languages). The demo uses the offline
`hashing` embedder, so the same issue in different languages appears as separate themes; with
`obsei[embeddings]` they are grouped (see [Themes](/guides/themes/)). Demo themes carry curated
labels; real themes are labelled from shared keywords or by your `labeler` model.

To rebuild the demo with the multilingual model (needs network to Hugging Face once):

```bash
uv run --extra embeddings obsei models download
uv run --extra embeddings obsei demo --embedder local --out docs/public/demo
```

`obsei demo` follows `OBSEI_EGRESS_MODE` (air-gapped by default), so it loads the model only from
the local cache (`OBSEI_MODELS_DIR`, or the fastembed cache) that `obsei models download` fills.
`--embedder` takes the same names as `themes.embedder`: `hashing`, `local` or `local:<model>`.
The embedder that built the demo is recorded as `embedder` in `data.json`.

Studio shows k-anonymous aggregates, stable themes with seven-day trends, a knowledge graph that
links themes to sources, languages, intents and sentiment, and redacted evidence for each theme.
It never shows authors and never edits data.

## Live

`obsei serve` hosts Studio at `/studio/`. Studio asks for `OBSEI_API_TOKEN` and keeps it for the
browser tab only. The **Ask** box uses `obsei ask` on the server.

## Static export

```bash
obsei studio --out site/      # index.html, app.js, styles.css and data.json
```

Host the folder anywhere (an internal bucket, Cloudflare Pages behind Access). The export holds
only k-anonymous aggregates and a few redacted quotes per theme.

## Slack

Create a Slack app with a slash command `/obsei` pointing to
`https://your-host/slack/commands`, set `SLACK_SIGNING_SECRET`, and allow `hooks.slack.com` in the
egress policy. Answers are posted to the channel with record-id citations.
