---
title: Studio
description: The read-only web UI with a knowledge-graph explorer.
sidebar:
  order: 8
---

[Open the demo](/demo/): eight weeks of synthetic feedback in eleven languages from app stores,
a help desk, an NPS survey, Bluesky and GitHub, with a login spike after an app update. No real
people or customers are in it; the contact details and ID numbers in a few records are made up
(checksum-valid, so redaction catches them).

Studio shows k-anonymous aggregates, stable themes with seven-day trends and a weekly sparkline
(themes whose last seven days at least doubled the seven before are marked **Rising**), a knowledge
graph that links themes to sources, languages, intents and sentiment, and redacted evidence for
each theme, with placeholders such as `<EMAIL>` highlighted. It never shows authors and never edits
data.

## Privacy panel

Every Studio (live, export and demo) has a **Privacy** panel, built from aggregates only, so the
viewer role sees it too:

- how often each redaction placeholder (`<EMAIL>`, `<PHONE>`, `<CARD>`, `<IBAN>`, `<IN_AADHAAR>`,
  `<BR_CPF>`, ...) occurs in stored text, and in how many records;
- the k-anonymity threshold, and how many themes and source, language or label groups it hides;
- how many distinct pseudonymised authors there are (never who they are);
- the egress mode (`air_gapped`, `private` or `hybrid`) of the server, in live mode only.

## Decisions

When `classify` stores fields (for example from a [decision model](/guides/models/#decision-models)
with `team`, `urgency` or yes/no fields), Studio shows a **Decisions** panel: k-anonymous counts per
answer (score levels in order) and the share of records marked for review because an answer was
below its confidence cutoff. Evidence lists each record's labels with the model's confidence.
Pipelines with [routes](/guides/routing/) also get a **Routes** chart: records per route rule.

## How the demo is built

`obsei demo` builds the static demo from the synthetic records in `obsei/demo.py`: it redacts them
as ingest would, labels them, groups themes, and exports a snapshot marked `demo`. Only the demo
shows a short guided intro, before-and-after redaction cards (the raw text exists only because the
data is synthetic; Studio never has raw text otherwise) and a few **Ask your data** answers recorded
from the dataset, citing record ids shown in its evidence. Demo records are routed with the routes
of `examples/decision-routing.yaml` without its refunds rule (billing chosen by the demo's `team`
field), using the same
routing code as a pipeline. In your deployment Ask uses your own
model, and agents get the same answers over MCP.

The demo's labels (sentiment, intent, team, urgency and an angry yes/no) come from Julia-1, a
144M-parameter decision model, run once on a CPU and committed as `obsei/demo_labels.json`, so the
build needs no model server. They are shown as the model produced them, mistakes included: 49% of
records are marked for review (see [known limits](/guides/models/#known-limits)). To label it again with a decision model, put its endpoint URL in an
environment variable:

```bash
export OBSEI_DEMO_DECISION_URL=...   # the decision endpoint URL your server documents
uv run obsei demo --decision-url-env OBSEI_DEMO_DECISION_URL \
  --save-labels packages/obsei/src/obsei/demo_labels.json --out docs/public/demo
```

The demo groups the same issue across languages with the multilingual model (needs network to
Hugging Face once):

```bash
uv run --extra embeddings obsei models download
uv run --extra embeddings obsei demo --embedder local --out docs/public/demo
```

`obsei demo` follows `OBSEI_EGRESS_MODE` (air-gapped by default), so it loads the model only from
the local cache (`OBSEI_MODELS_DIR`, or the fastembed cache) that `obsei models download` fills.
`--embedder` takes the same names as `themes.embedder`: `hashing`, `local` or `local:<model>`;
with the offline `hashing` embedder each language forms its own theme. The embedder that built the
demo is recorded as `embedder` in `data.json`. Demo themes carry curated labels; real themes are
labelled from shared keywords or by your `labeler` model.

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
