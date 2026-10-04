# obsei roadmap

obsei is being rebuilt as an open-source, self-hosted, privacy-first Voice of Customer platform built
for AI agents. Enterprises run it entirely inside their own environment with their own sources,
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

## Phases

| Phase | Target | Scope | Gate |
| --- | --- | --- | --- |
| Setup | Weeks 1-3 | New codebase skeleton, CI, release automation, security baseline | Green CI; publishing tested |
| 0.1 Private core | Months 1-3 | Record schema, encrypted DuckDB, redaction, pseudonyms, TTL / forget / export, no-egress mode; LiteLLM and local models; CSV, JSON Lines and declarative REST; App Store, Google Play, GitHub, RSS; Slack, webhook, GitHub Issues and Parquet sinks; CLI; Docker | Air-gapped end-to-end test passes |
| 0.2 MCP and Claude plugin | Months 3-5 | MCP read tools, Claude plugin, GitHub Action recipes; `obsei serve` with webhook intake; App Store Connect, Hacker News, Bluesky, YouTube; plugin scaffold; docs site | Listed in the MCP Registry and Claude directory |
| 0.3 Enterprise BYO | Months 5-7 | SQL, MCP-client and file-drop sources; Zendesk, Intercom, Freshdesk, email; Jira, Linear and warehouse sinks | One enterprise design partner in production |
| 0.4 Themes and Studio | Months 7-10 | Embeddings, dedupe, stable themes, k-anonymous views, `ask`; Gong; read-only Studio with a knowledge graph explorer; Slack bot; static demo | Demo live; release candidate tested |
| 1.0 | Months 12-14 | Stable API and schema; write tools behind an approval queue; ChatGPT connector; full knowledge graph | |

## Releases

The first stable release is **1.0.0**. Milestones ship earlier as PyPI pre-releases, which
`pip install obsei` ignores unless `--pre` is passed: 0.1 as `1.0.0a1`, 0.2 as `1.0.0a2`,
0.3 as `1.0.0b1`, 0.4 as `1.0.0rc1`. The public launch, with Show HN, is 1.0.0.

## Not planned (contributor-gated)

Hosted SaaS, internal employee-channel analytics, scrapers that circumvent platform protections,
default-on telemetry, and per-vendor native connectors beyond the list above.
