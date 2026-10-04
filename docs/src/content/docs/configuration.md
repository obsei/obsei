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

## How a run works

1. Each source resumes from its saved cursor and yields records.
2. Records are redacted, then compared with the stored copy; unchanged records stop here.
3. Enrichers label new or changed records.
4. Every sink receives the batch. Only then is the batch stored and the cursor advanced, so a
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
