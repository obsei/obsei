---
title: Migrate from 0.0.x
description: How obsei 1.0 differs from the 0.0.x toolkit, what maps to what, and how to stay on the old version.
sidebar:
  order: 11
---

obsei 0.0.x was an "observe, analyze, inform" toolkit: Python classes you wired together in your
own code. 1.0 is a rewrite with a new codebase, not an upgrade. There is no compatibility layer,
and 0.0.x code will not run against it.

## Concepts

| 0.0.x | 1.0 |
| --- | --- |
| Observer | Source (`sources:` in a pipeline) |
| Analyzer | Enricher (`enrichers:`) |
| Informer | Sink (`sinks:`) |
| Workflow, built and run in Python | Pipeline in `obsei.yaml`, run with `obsei run` or `obsei serve` |
| Workflow store (SQL state) | Encrypted DuckDB store, which also skips records it has seen |
| PII anonymizer analyzer, opt-in | Redaction and author pseudonyms at ingest, on by default |
| Transformer classifiers and sentiment analyzers | `classify` with your LLM or a decision model ([Models](/guides/models/)) |

Configuration is declarative: a config file can name plugins but never import arbitrary code.
Run `obsei init` for a starting `obsei.yaml`, then see [Configuration](/configuration/).

## Connectors

| 0.0.x | 1.0 |
| --- | --- |
| App Store scraper | `appstore` (public review feed) or `appstoreconnect` (official API) |
| Play Store scraper | `playstore` (official Android Publisher API) |
| YouTube scraper | `youtube` (YouTube Data API key) |
| Email | `imap` |
| Pandas DataFrame | `csv` and `jsonl` sources, `parquet` sink |
| HTTP informer | `webhook` sink |
| Slack, Jira | `slack`, `jira` sinks |
| Zendesk informer | `zendesk` is now a source; send tickets with `webhook` or a plugin |

## What's gone

- Twitter/X, Facebook, Google Maps reviews, Google News and the web crawler.
- The Reddit scrapers. Reddit is a community plugin that reads RSS
  ([install it from Git](/guides/sources/#reddit-plugin)).
- The Elasticsearch and logger informers. Use the `sql`, `parquet` or `webhook` sink, or
  `obsei try` to inspect records.
- The translator and NER analyzers. Feedback stays in its original language, and names are found
  only for redaction (`obsei[names]`).

Missing a connector? Write a [plugin](/reference/plugins/) for it.

## Staying on 0.0.x

Pin below 1.0:

```bash
pip install "obsei<1"
```

Until 1.0.0 is released, a plain `pip install obsei` still gives 0.0.15, but that changes at the
launch, so pin now. The 0.0.x code lives on the
[`legacy/0.0.x`](https://github.com/obsei/obsei/tree/legacy/0.0.x) branch.
