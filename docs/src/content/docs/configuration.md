---
title: Configuration
description: The obsei.yaml file.
---

`obsei.yaml` declares pipelines built only from registered plugins, so a config file can never
import arbitrary code. Secrets never go in the file: fields ending in `_env` name the environment
variable that holds the value.

```yaml
version: 1

store:
  path: obsei.duckdb        # OBSEI_DB overrides
  unencrypted: false        # true only on an encrypted disk
                            # air-gapped: pre-install httpfs, set OBSEI_DUCKDB_EXTENSIONS

privacy:
  redact: true
  regions: [global, north_america, uk, eu, latam, apac, india, africa]

egress:                     # optional; otherwise OBSEI_EGRESS_MODE / OBSEI_EGRESS_ALLOW
  mode: private
  allowed_hosts: [my-tenant.openai.azure.com]

llms:
  local:
    base_url: http://localhost:11434/v1
    model: qwen3:8b
  azure:
    base_url: https://my-tenant.openai.azure.com/openai/v1
    model: gpt-5-mini
    api_key_env: AZURE_OPENAI_API_KEY
    max_requests: 2000

plugins: [reddit]           # installed plugins allowed to load (reddit: see Sources)

pipelines:
  - name: reviews
    batch_size: 100
    sources:
      - key: ios
        type: appstore
        config: {app_id: "284882215", countries: [us, de, br, jp, in, ng]}
    enrichers:
      - type: classify
        config: {llm: local, fallback_llm: azure, threshold: 0.7}
    sinks:
      - type: slack
        config: {when: {classify.intent: [bug, churn_risk]}}
```

Sinks take an optional `key` (default: their type), and a pipeline can add ordered `route:` rules
that send each record to the sinks of the first rule it matches; see [Routing](/guides/routing/).

## Enrichers

Enrichers run in the order listed, on new or changed records only.

| Type | What | Model |
| --- | --- | --- |
| `filter` | One yes/no question per record; matching records are tagged or dropped | decision |
| `classify` | Sentiment, intent, language and your own fields, with a confidence | chat or decision |

`classify` takes `llm`, `fallback_llm`, `threshold`, `min_confidence`, `sentiments`, `intents` and
`fields`; see [Models](/guides/models/#decision-models) for decision endpoints, option
descriptions and cutoffs. Put `filter` first so dropped records never reach the classifier:

```yaml
enrichers:
  - type: filter
    config:
      llm: julia                 # an llms entry with api: decision
      question: Is this spam rather than a real customer request?
      yes_means: prize scams, phishing links, advertising or bulk mail   # optional, with no_means
      no_means: a customer writing about a product, an account or a bill
      threshold: 0.8             # probability of yes from which a record matches (default 0.5)
      action: drop               # or tag (default): keep it with filter.match: true
  - type: classify
    config: {llm: julia, fallback_llm: local}
```

Dropped records are not classified, delivered or stored; the run summary counts them
(`dropped 3`). A source that returns the same record again (a feed without a cursor) has it checked
again. With `action: tag`, sinks can skip matches with `when: {filter.match: ["false"]}`.

## Ask

`obsei ask`, `POST /api/ask` and the Slack command answer from your feedback with `ask_llm`. Add
`ask_judge`, a decision endpoint, to check each answer against the records it cites: the judge gets
only the question, the answer and the cited records (redacted, as stored) and answers "Is every
statement in the answer supported by the quoted records?".

```yaml
ask_llm: local
ask_judge: kev               # an llms entry with api: decision
ask_judge_threshold: 0.5     # default
```

The CLI prints `grounded: 0.93`, and below the threshold warns that the answer may not be
supported. The API returns `grounded` and `possibly_unsupported`, and Slack replies carry a
warning line. Judging needs a capable model: in our tests Julia-1 did not separate supported from
unsupported answers, so use a 4B or larger decision model (Kev-4B, lev, Clef-Flash) as the judge.

## How a run works

1. Each source resumes from its saved cursor and yields records.
2. Records are redacted, then compared with the stored copy; unchanged records stop here.
3. Enrichers label new or changed records; a `filter` with `action: drop` removes records here.
4. Records go to sinks: with a [`route:`](/guides/routing/), each sink a route names gets only the
   records routed to it, and every other sink gets the batch through its own `when`. Only then is the batch stored and the cursor advanced, so a
   failed run retries the same batch (at-least-once; sinks are idempotent by record id).

A failing pipeline is reported and the others still run; `obsei run` then exits with status 1.

## Scheduling

Set `every_minutes` on a pipeline and `obsei serve` runs it on that schedule, sharing the server's
database. DuckDB allows a single writer, so do not point a separate `obsei run` at a database that
`obsei serve` holds. `themes.auto: true` updates themes after each scheduled run, and
`GET /api/runs` reports the last run of each pipeline.

```yaml
themes:
  auto: true
pipelines:
  - name: reviews
    every_minutes: 60
    sources: [...]
```

Without a server, `obsei run --every 60` repeats the run every hour.
