---
title: Studio
description: The read-only web UI with a knowledge-graph explorer.
sidebar:
  order: 7
---

[Open the demo](/demo/) (synthetic feedback in eight languages). The demo uses the offline
`hashing` embedder, so the same issue in different languages appears as separate themes; with
`obsei[embeddings]` they are grouped (see [Themes](/guides/themes/)).

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
