---
title: Sinks
description: Where obsei delivers feedback.
sidebar:
  order: 2
---

Sinks receive only new or changed records, after redaction and enrichment. Outbound sinks are
checked against the egress policy when the pipeline starts.

| Type | What | Idempotency | Status |
| --- | --- | --- | --- |
| `webhook` | JSON batches, optional HMAC signature over `{X-Obsei-Timestamp}.{body}`; authors omitted by default | record ids in the payload | beta |
| `slack` | Messages for matching feedback, capped per run | at-least-once | verified |
| `github_issues` | One issue per matching record | hidden marker, searched before creating | beta |
| `jira` | One issue per matching record (Cloud with ADF, or Data Center) | `obsei-rec_...` label | beta |
| `linear` | One issue per matching record | marker in the description | verified |
| `parquet` | Parquet files for notebooks and lakes | file named by batch content | beta |
| `sql` | Upsert into a table in any SQLAlchemy database or warehouse | delete and insert by id | beta |

`verified` means a live test in
[`packages/obsei/tests/live`](https://github.com/obsei/obsei/tree/master/packages/obsei/tests/live)
exercises the connector end to end against the real service or data; `beta` connectors are
covered by mocked tests only.

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
`{classify.fields.urgency: [today, right now]}` or `{filter.match: ["false"]}`. Instead of a list,
a condition can test what a decision model stores: `{is: bug, min_confidence: 0.8}`,
`{gte: today}` on a score field, `{min_probability: 0.7}` on a yes/no field, and `review: false`
to skip records flagged for review. See [Routing](/guides/routing/#conditions) for every condition.

## Routes

`when` filters fan out: each sink checks every record. To send each record to one set of sinks,
give sinks a `key` and add ordered `route:` rules to the pipeline; the first match wins, with a
`default` and a `review` shortcut for records still flagged after the fallback:

```yaml
sinks:
  - {key: jira, type: jira, config: {base_url: https://acme.atlassian.net, project_key: SUP, when: {}}}
  - {key: oncall, type: slack, config: {webhook_url_env: ONCALL_SLACK_WEBHOOK_URL}}
  - {key: lake, type: parquet, config: {directory: lake}}
route:
  - name: urgent-bugs
    when: {classify.intent: [bug], classify.fields.urgency: {gte: today}}
    sinks: [jira, oncall]
  - default: [lake]
```

Sinks no route names still receive every record through their own `when`. The
[Routing](/guides/routing/) guide covers the rules, the stored `route` enrichment and a full
example.
