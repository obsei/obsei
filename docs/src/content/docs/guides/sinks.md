---
title: Sinks
description: Where obsei delivers feedback.
sidebar:
  order: 2
---

Sinks receive only new or changed records, after redaction and enrichment. Outbound sinks are
checked against the egress policy when the pipeline starts.

| Type | What | Idempotency |
| --- | --- | --- |
| `webhook` | JSON batches, optional HMAC signature; authors omitted by default | record ids in the payload |
| `slack` | Messages for matching feedback, capped per run | at-least-once |
| `github_issues` | One issue per matching record | hidden marker, searched before creating |
| `jira` | One issue per matching record (Cloud with ADF, or Data Center) | `obsei-rec_...` label |
| `linear` | One issue per matching record | marker in the description |
| `parquet` | Parquet files for notebooks and lakes | file named by batch content |
| `sql` | Upsert into a table in any SQLAlchemy database or warehouse | delete and insert by id |

## Filters

Issue and chat sinks take `when` (labels from enrichers) and `max_rating`:

```yaml
- type: jira
  config:
    base_url: https://acme.atlassian.net
    project_key: APP
    when: {classify.intent: [bug]}
    max_rating: 2
```

`when` reads nested fields and yes/no values too, e.g.
`{classify.fields.urgency: [today, right now]}` or `{filter.match: ["false"]}`.
