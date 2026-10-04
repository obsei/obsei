---
title: Routing
description: Send each record to the right sinks with filters and ordered routes, using the labels, confidences and scores decision models store.
sidebar:
  order: 3
---

Every sink can filter what it receives with `when`. A pipeline can also list ordered `route:`
rules that pick, for each record, which named sinks get it. Both use the same conditions, read
from the enrichments a record carries (usually `classify`, and `filter` for spam).

## Filters and routes

**Filters fan out.** Each sink checks every record against its own `when` and `max_rating`. One
record can reach several sinks, or none. This is how pipelines without `route:` work.

**Routes pick one rule.** Rules are checked in order and the first match wins; the record goes
to that rule's sinks only. Use routes when destinations should not overlap: an urgent bug pages
on-call and opens a Jira issue, but does not also land in the billing channel.

**`default`** is the last rule: records no earlier rule matched go to its sinks. Without it they
go to no routed sink.

**`review`** is a shortcut for records still flagged for review. A decision model marks a record
with `review: true` when an answer falls below its cutoff; with a `fallback_llm` the chat model
relabels it and the flag goes away, so `review` catches only what the fallback could not settle.
Put it first so uncertain labels never open tickets.

### Which sinks routes control

Sinks are named by `key`; without one a sink's key is its type. Routes refer to keys.

- A sink named by any route gets only the records routed to it, then still applies its own
  `when` and `max_rating`. Give it `when: {}` when the route should decide alone (`jira`,
  `github_issues` and `linear` otherwise keep their default `classify.intent: [bug,
  feature_request]`).
- A sink no route names keeps today's behaviour: every record, through its own `when`. An audit
  webhook or a warehouse table can sit next to routes this way.
- In a pipeline with `route:`, keys must be unique: give two sinks of the same type their own
  `key`. Without `route:`, unkeyed sinks of one type still load as before.

Each record is stored with a `route` enrichment, `{"rule": "urgent-bugs", "sinks": ["jira",
"oncall"]}`, or `{"rule": "unrouted", "sinks": []}` when nothing matched. Parquet, SQL and
webhook sinks export it with the other enrichments, `feedback_stats` and the store group by
`route`, and Studio shows a **Routes** chart once routed records exist (groups under the
k-anonymity threshold are hidden, as for every chart).

## Conditions

A condition maps a dotted path to a test. `classify.intent` and `classify.sentiment` are labels,
`classify.fields.<name>` a field you defined, `filter.match` the spam filter's answer. All
conditions in one `when` must hold.

| Condition | Matches |
| --- | --- |
| `classify.intent: [bug, churn_risk]` | the value is one of these (yes/no values are `"true"` and `"false"`) |
| `classify.intent: {is: bug}` | the same; `is` takes one value or a list |
| `classify.intent: {is: bug, min_confidence: 0.8}` | and the answer's confidence is at least 0.8 |
| `classify.fields.urgency: {gte: today}` | a score field at or above a level, by level order |
| `classify.fields.urgency: {lte: this week}` | at or below a level |
| `classify.fields.urgency: {gte: 2.5}` | the expected score (0 = lowest level, may be fractional) |
| `classify.fields.asks_for_refund: {is: true}` | a yes/no field answered yes |
| `classify.fields.asks_for_refund: {min_probability: 0.7}` | the probability of yes is at least 0.7 |
| `classify.intent: {is: [bug, question], min_probability: 0.9}` | the listed options together have at least 0.9 |
| `filter.match: {min_probability: 0.9}` | the filter's probability of yes |
| `review: true` | an enricher flagged the record for review (`false`: not flagged) |
| `max_rating: 2` | rated 2 or lower; unrated records do not match |

Where the numbers come from:

- **`min_confidence`** uses the per-question confidence a decision model stores
  (`classify.confidences`). Chat-model results have one overall confidence, which is used
  instead.
- **`min_probability`** uses the stored per-question probabilities. For chat-model results it
  is approximated from the overall confidence: the confidence when the value is a target, one
  minus it otherwise.
- **`gte` / `lte` with a level** compare positions in the field's `levels`, which `classify`
  stores with each result; for records stored without them, routes use the levels in the
  pipeline's `classify` config.
  **With a number** they compare the decision model's expected score, or the level's position
  for chat-model results.

A record without the enrichment, or without the field, matches no condition on it.

Conditions are checked when the config loads. Errors name the pipeline and the sink or rule,
for example `pipeline 'tickets', route 2 (urgent-bugs): when.classify.fields.urgency: 'soon' is not one of the
levels ['can wait', 'this week', 'today', 'right now']`. Level names are checked against the
pipeline's `classify` fields; `gte` and `lte` with a level need a score field.

The same conditions work in a sink's `when`, so a single sink can say
`when: {classify.intent: {is: bug, min_confidence: 0.8}, review: false}`. Existing lists of
values keep working unchanged.

## Route rules

```yaml
route:
  - review: [review]                        # records still flagged for review
  - name: urgent-bugs                       # optional; shown in analytics
    when: {classify.intent: [bug], classify.fields.urgency: {gte: today}}
    sinks: [jira, oncall]
  - when: {classify.intent: [billing]}      # unnamed: called "billing" after its sinks
    sinks: [billing]
  - default: [lake]                         # must be last
```

Each rule is exactly one of `when` with `sinks`, `review` or `default`. `name` is optional; an
unnamed rule is called after its sinks joined with `+` (`jira+oncall`), `review` and `default`
after themselves. Names must be unique; `unrouted` is reserved. `sinks: []` routes matching
records nowhere, which keeps them out of the default.

## Full example

Support tickets labelled by a decision model, with a chat model for hard cases. Uncertain tickets
go to a review channel, urgent bugs open a Jira issue and page on-call, billing and refunds go to
the billing channel, and everything else lands in Parquet. An audit webhook, named by no route,
receives every ticket.

```yaml
pipelines:
  - name: tickets
    sources:
      - key: zendesk
        type: zendesk
        config: {subdomain: acme}
    enrichers:
      - type: classify
        config:
          llm: julia
          fallback_llm: ollama
          threshold: 0.6
          intents: [bug, billing, how_to, feature_request, churn_risk, praise, other]
          fields:
            urgency:
              description: How soon does the customer need this resolved?
              levels: [can wait, this week, today, right now]
            asks_for_refund:
              type: yesno
              description: Does the customer ask for money back?
              yes_means: asks for a refund, a chargeback or money back
              no_means: does not ask for money back
    sinks:
      - key: jira
        type: jira
        config: {base_url: https://acme.atlassian.net, project_key: SUP, when: {}}
      - key: oncall
        type: slack
        config: {webhook_url_env: ONCALL_SLACK_WEBHOOK_URL}
      - key: billing
        type: slack
        config: {webhook_url_env: BILLING_SLACK_WEBHOOK_URL}
      - key: review
        type: slack
        config: {webhook_url_env: REVIEW_SLACK_WEBHOOK_URL}
      - key: lake
        type: parquet
        config: {directory: support-lake}
      - key: audit                            # no route names it: gets every ticket
        type: webhook
        config: {url: https://audit.internal/obsei}
    route:
      - review: [review]
      - name: urgent-bugs
        when:
          classify.intent: {is: bug, min_confidence: 0.8}
          classify.fields.urgency: {gte: today}
        sinks: [jira, oncall]
      - name: billing
        when: {classify.intent: [billing]}
        sinks: [billing]
      - name: refunds
        when: {classify.fields.asks_for_refund: {min_probability: 0.7}}
        sinks: [billing]
      - default: [lake]
```

A ticket that says "Checkout is down, none of our customers can pay" with intent `bug` at 0.95
and urgency `right now` matches `urgent-bugs`: one Jira issue, one on-call message, nothing in
billing or Parquet, and a copy to the audit webhook. A "how do I export invoices" question
matches nothing until `default` and lands in Parquet with `route.rule: default`.

`obsei run` reports deliveries per sink key (`sent jira=1, oncall=1, lake=12, ...`), and
`feedback_stats(group_by="route")` counts records per rule. The complete config, with sources,
the spam filter and a local sample, is in
[examples/decision-routing.yaml](https://github.com/obsei/obsei/blob/master/examples/decision-routing.yaml).
