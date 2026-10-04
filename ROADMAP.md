# obsei roadmap

obsei is an open-source, self-hosted, privacy-first Voice of Customer platform built for AI agents. Enterprises run it entirely inside their own environment with their own sources,
models and agents; hobbyists run the same code on a laptop for free.

The project is maintained part-time with heavy automation, so scope is deliberately tight. Anything
not listed below ships only when a contributor builds and maintains it.

## Principles

- **Privacy by design:** redact PII and pseudonymise authors at ingest, keep models inside your
  boundary, no telemetry, retention and erasure built in, air-gapped mode.
- **Bring your own:** sources, keys, LLMs and agents.
- **Generic first:** declarative REST, SQL, MCP-client, webhook and file-drop sources cover most
  systems; native connectors only where bulk history or verbatim text needs them.
- **AI-native:** MCP server first; agents act only through an approval queue.
- **One monorepo:** library, CLI, MCP server, REST server, web UI, platform apps, docs and every plugin.

## Status

| Phase | Status | Scope |
| --- | --- | --- |
| Setup | Done | Codebase skeleton, CI, release automation, security baseline |
| 0.1 Private core | Done | Record schema, encrypted DuckDB, redaction, pseudonyms, forget / export / audit, no-egress mode, bring-your-own LLM, first sources and sinks, CLI, Docker |
| 0.2 MCP and Claude plugin | Done | MCP read tools, Claude plugin, GitHub Action, `obsei serve` with webhook intake, App Store Connect, Hacker News, Bluesky, YouTube, plugin workspace, docs site |
| 0.3 Enterprise BYO | Done | SQL, MCP-client, file-drop, IMAP, Zendesk, Freshdesk, Intercom; Jira, Linear and SQL sinks; role-based access and SSO proxy |
| 0.4 Themes and Studio | Done | Embeddings (offline and multilingual), dedupe, stable themes, k-anonymous views, `ask`, Gong, Studio with a knowledge graph, Slack command, static demo, name redaction |
| 0.5 Decisions and routing | Done | Decision models (Julia-1, Clef) with probabilities, confidence fallback to a chat model or a human, `filter` enricher, grounding judge for `ask`, ordered routes on model confidence, Studio privacy, decisions, trends and routes panels |
| Release candidate | In progress | `1.0.0rc1` published. Before 1.0: weekly live-connector checks green, one design partner in production, listed in the MCP Registry and Claude plugin directory |
| 1.0 | Planned | Stable API and schema; write tools behind an approval queue; ChatGPT connector; fuller knowledge graph; Show HN launch |

## Releases

Everything above ships as PyPI pre-releases (`1.0.0a1`, then `1.0.0rc1`, `1.0.0rc2`, ...), which `pip install obsei`
ignores unless `--pre` is passed or the requirement names one (`obsei>=1.0.0rc1`). The first stable release and public launch is **1.0.0**.

## Not planned (contributor-gated)

Hosted SaaS, internal employee-channel analytics, scrapers that circumvent platform protections,
default-on telemetry, and per-vendor native connectors beyond the list above.
