---
title: What's new in 1.0
description: What obsei 1.0 adds, and how to upgrade from 0.0.x or a release candidate.
---

obsei 1.0 is a rewrite of the 0.0.x library: a self-hosted pipeline that redacts personal data
at ingest, labels and groups feedback into themes, and sends what matters to your tools. Coming
from 0.0.x, start with the [migration guide](/guides/migrate-from-0-0/). Every change is in the
[changelog](https://github.com/obsei/obsei/blob/master/packages/obsei/CHANGELOG.md).

## Highlights

- **A five-minute first run.** `obsei init` writes the project, sample data with synthetic PII and
  `.obsei/secrets.env`. `obsei try` previews redacted, labelled records from the project or from
  any public link or file, without storing anything ([Quickstart](/quickstart/)).
- **An in-process classifier by default.** `api: local` runs bge-m3-zeroshot-v2.0 on your machine
  with `obsei[local]`; no model server is needed. `themes.embedder: auto` picks the multilingual
  embedder when `obsei[embeddings]` is installed ([Models](/guides/models/)).
- **Measure and correct.** `obsei eval` scores the classifier on a labelled CSV and suggests
  cutoffs, `obsei correct` stores human labels, and `obsei reprocess` relabels stored records
  ([Classify](/guides/classify/)).
- **Setup without YAML.** `obsei add`, `obsei check` and `obsei integrations`, field descriptions
  everywhere, and a published [JSON Schema](https://docs.obsei.com/schema/obsei.schema.json) for
  editor completion ([Set up without editing YAML](/guides/setup/)).
- **Alerts.** Theme spikes, new themes, digests, review-queue size and pipeline health, with
  cooldown, snooze and acknowledge ([Alerts](/guides/alerts/)).
- **Signed events and notifications.** The `webhook` sink sends CloudEvents signed per Standard
  Webhooks, retries and logs deliveries; the `notify` sink reaches Telegram, Discord, email and
  100+ services ([Sinks](/guides/sinks/)).
- **Safer agents.** MCP results mark customer text `untrusted`, and `propose_issue` queues issues
  for `obsei approvals approve` ([MCP](/guides/mcp/)). The MCP server is part of the core package,
  and plugins for Claude Code, Codex, Copilot, Cursor and Gemini CLI install it in one line
  ([AI tools](/guides/ai-tools/)).
- **Connector status.** Each source and sink is marked `verified` (a live test against the real
  service) or `beta` ([Sources](/guides/sources/)).

## Upgrading from a release candidate

- Install with a version floor, `uvx --from "obsei>=1.0" obsei ...`; a plain `uvx obsei` can reuse
  a cached release candidate.
- `obsei[mcp]` is no longer needed; the extra still exists, empty.
- Webhook receivers: events are CloudEvents with records under `data.records`, signed with the
  `webhook-id`, `webhook-timestamp` and `webhook-signature` headers. The `X-Obsei-Timestamp` and
  `X-Obsei-Signature-256` headers are gone, for the sink and for `obsei serve` intake
  ([Serve](/guides/serve/)).
- Projects created before rc5 have no `.obsei/secrets.env`; keep exporting `OBSEI_DB_KEY` and
  `OBSEI_PSEUDONYM_SALT`, or move them into that file.
- The store migrates itself on first open (deliveries, alert state and approvals tables).
