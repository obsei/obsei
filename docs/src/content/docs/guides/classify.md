---
title: Your own labels and questions
description: Change the intents and sentiments classify picks from, add your own choice, score and yes/no questions, and route on the answers.
sidebar:
  order: 2.5
---

The `classify` enricher answers two questions for every record out of the box, sentiment and
intent, and you can change both and add your own. Each question is answered with a confidence,
and answers below the cutoff are marked for review.

## Change the labels

`intents` and `sentiments` take a list, or a mapping of each label to a one-line description.
Described labels are picked more reliably, so describe the ones that are specific to you:

```yaml
enrichers:
  - type: classify
    config:
      llm: default
      intents:
        bug: something is broken, errors, crashes or does not work as documented
        billing: charges, invoices, refunds, payment methods or prices
        feature_request: asks for a new feature, option or improvement
        churn_risk: threatens to cancel, downgrade or move to a competitor
        other: none of the above
```

Keep an `other` option, so a record that fits nothing does not get forced into a wrong label.

## Add a question

Add entries under `fields`; the key is the question's name. There are three kinds a local or
decision model answers (a chat model can also answer free `text` fields):

```yaml
      fields:
        area:                         # choice: one of the options
          description: Which part of the product is this about?
          choices: {mobile: the iOS or Android app, web: the browser app, api: the public API}
        urgency:                      # score: one of 2 to 10 levels, lowest first
          description: How soon does the customer need this resolved?
          levels: [can wait, this week, today, right now]
        asks_for_refund:              # yes/no
          type: yesno
          description: Does the customer ask for money back?
          yes_means: asks for a refund, a chargeback or money back
          no_means: does not ask for money back
```

`description` is what the model is asked. For yes/no questions, describe both answers with
`yes_means` and `no_means`: small models answer a choice between two described options far better
than a bare yes/no (local models require both). Each answer is stored under
`classify.fields.<name>`; yes/no answers are `true` or `false`.

Your editor completes and checks these keys when `obsei.yaml` starts with the schema line (see
[Set up without editing YAML](/guides/setup/#editor-autocomplete)).

## Check the answers

```bash
obsei try --limit 20          # the labels, with their confidence, on your own feedback
obsei eval my-labelled.csv    # accuracy per question and a suggested cutoff for each
```

`obsei eval` reads a CSV with a `text` column and a column per question (`intent`, `urgency`,
`asks_for_refund`, ...) and suggests a `min_confidence` per question; see
[Measure on your own data](/guides/models/#measure-on-your-own-data). Set cutoffs per question:

```yaml
      min_confidence: {intent: 0.6, urgency: 0.5, asks_for_refund: 0.7}
```

## Route on the answers

Sinks filter with `when`, and ordered `route:` rules send each record to one set of sinks:

```yaml
    sinks:
      - {key: oncall, type: slack, config: {webhook_url_env: ONCALL_WEBHOOK_URL}}
      - {key: billing, type: slack, config: {webhook_url_env: BILLING_WEBHOOK_URL}}
      - {key: lake, type: parquet, config: {directory: lake}}
    route:
      - review: [lake]                          # uncertain answers: no ticket, no page
      - name: urgent-bugs
        when: {classify.intent: [bug], classify.fields.urgency: {gte: today}}
        sinks: [oncall]
      - name: refunds
        when: {classify.fields.asks_for_refund: ["true"], classify.intent: {is: billing, min_confidence: 0.7}}
        sinks: [billing]
      - default: [lake]
```

`gte` and `lte` compare score levels in the order you listed them, and obsei checks on load that
the levels a route names are levels of that field. Add the two Slack
sinks with `obsei add slack --key oncall` and `obsei add slack --key billing`; each gets its own
webhook secret. [Routing](/guides/routing/) lists every condition.

After changing questions or labels, `obsei reprocess` relabels the records already stored and
keeps human corrections.
