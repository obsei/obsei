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
| 1.0 work | Done | In-process classifier as the default, `obsei eval`, `reprocess` and corrections, theme spike, digest, review and health alerts, signed event webhooks and the Apprise `notify` sink, approval queue for agent writes, untrusted-text marking in MCP, a first run with generated secrets and `obsei try <link>`, guided setup (`obsei add`, `check`, `integrations`, editor schema), plugins for Claude, Codex, Copilot, Cursor and Gemini, MCP Registry listing |
| 1.0 | Released (2026-10-15) | First stable release. Stable within 1.x, changing only by addition: the record schema, `obsei.yaml` (version 1), the CLI, MCP tools and the approval queue, the plugin protocol, alert config and the webhook event format |

## Next

Open for contributors; not started.

- **Design partner case study:** one organization running 1.x in production, written up.
- **ChatGPT connector:** a public MCP endpoint with OAuth 2.1 (ChatGPT rejects static tokens);
  until then the [tunnel recipe](https://docs.obsei.com/guides/ai-tools/) covers private use.
- **Hierarchical labels:** a taxonomy file with facets and parent labels for `classify`, building
  on `obsei eval` and corrections.
- **Fuller knowledge graph** in Studio.
- **Framework adapters:** a dlt source and a LangChain document loader.
- **More benchmarked models:** Clef-Flash and Qwen3 1.7B and 4B on the demo
  [benchmark](https://docs.obsei.com/guides/models/#benchmark) (`obsei eval --demo`).
- **Cloudflare Workers AI** for chat and embeddings (decision models already work through its URL).

## Releases

`pip install obsei` installs the latest release. Releases follow semantic versioning: fixes ship as
patch releases (1.0.1, 1.0.2, ...) and additions as minor releases.

## Not planned (contributor-gated)

Hosted SaaS, internal employee-channel analytics, scrapers that circumvent platform protections,
default-on telemetry, and per-vendor native connectors beyond the list above.
