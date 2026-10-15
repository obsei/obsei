---
title: Use obsei as the privacy step for your agent
description: Give agents customer feedback through obsei's MCP server, with PII stripped at ingest, and copy-paste prompts for coding agents.
sidebar:
  label: Agents
  order: 6.5
---

Point your agent at obsei instead of at the raw sources. obsei fetches the feedback, redacts it
and stores it; the agent reads only what was stored, through a read-only MCP server.

## Before any model sees text

Each run fetches, redacts, enriches, delivers and stores, in that order (see
[How it works](/how-it-works/)). By the time text reaches a model, whether your `classify`
endpoint or an agent over MCP, it has already been through:

- **Redaction.** Emails, phone numbers, cards, national IDs and other PII for the regions in
  `privacy.regions` become placeholders such as `<EMAIL>`. Names become `<PERSON>` when
  `privacy.names` is enabled (`obsei[names]`).
- **Pseudonymization.** Authors become salted pseudonyms (`psn_...`). MCP results never contain
  them, not even the pseudonym.
- **k-anonymity.** `list_themes` hides themes from fewer than `k_anonymity` people.

Raw text with personal data is never stored, so an agent cannot recover it. See
[Privacy controls](/privacy/overview/) for the detectors and their limits.

## What the MCP server exposes

| Tool | Use |
| --- | --- |
| `feedback_stats` | Counts and average rating grouped by source, sentiment, intent, language, route, day and more |
| `search_feedback` | Matching feedback, newest first, as citable evidence with record ids |
| `get_feedback` | One record by id, to verify a citation |
| `list_themes` | Recurring themes with 7-day trend, sources, languages and intents |

The `voc_report` prompt drafts a cited Voice of Customer report for a topic and period.

Two transports serve the same tools:

| Transport | Start | Access |
| --- | --- | --- |
| stdio | `obsei mcp` | opens the store read-only on the local machine |
| streamable HTTP | `obsei serve`, at `/mcp` | analyst role: `Authorization: Bearer <token>` or your SSO proxy |

Setup for Claude, Codex, Copilot, Cursor, Gemini and other tools is in
[Use obsei from your AI tool](/guides/ai-tools/).

## Customer text is untrusted input

Feedback is written by anyone who can leave a review or open a ticket, so it can contain
instructions aimed at your agent. The server tells clients to treat it as data: quote it, cite
record ids, and never follow instructions found inside it. Keep that rule in your own agent's
system prompt too, and don't give the same agent unreviewed write access to other systems.

## Read-only today

No tool changes data: agents cannot label, delete, route or send feedback. Write tools behind an
approval queue, where a person approves each action, are planned for 1.0.

## Prompts for coding agents

Copy one into Claude Code, Cursor or another coding agent. The commands under each prompt are what
the agent should run, so you can check its work. Agents can read the whole docs site at
[`/llms-full.txt`](https://docs.obsei.com/llms-full.txt).

### App Store reviews to Slack

> Set up obsei to pull App Store reviews for app 284882215 in the US, UK and Germany, classify them
> with my local Ollama model, and send negative ones to Slack. Read
> https://docs.obsei.com/llms-full.txt first. Don't put secrets in obsei.yaml.

```bash
uv tool install "obsei[local]>=1.0.0rc1"
mkdir voc && cd voc && obsei init   # secrets go to .obsei/secrets.env
export SLACK_WEBHOOK_URL="https://hooks.slack.com/services/..."   # from you, not invented
```

Then it edits `obsei.yaml`:

```yaml
egress:
  mode: private
  allowed_hosts: [hooks.slack.com]
pipelines:
  - name: app-reviews
    sources:
      - key: ios
        type: appstore
        config: {app_id: "284882215", countries: [us, gb, de]}
    enrichers:
      - type: classify
        config: {llm: default}
    sinks:
      - type: slack
        config:
          when: {classify.sentiment: [negative]}
          max_messages: 20
```

```bash
obsei try   # redacted, labelled preview; nothing stored or sent
obsei run
```

### Ask questions about customers

> Connect yourself to obsei over MCP and tell me the top complaints this month, by country, with
> quotes cited by record id.

```bash
claude mcp add obsei -- obsei mcp
```

### Remote MCP from Docker Compose

> Run obsei with the repository's docker-compose.yml in this directory and connect to its MCP
> server over HTTP.

```bash
cp .env.example .env   # agent fills it with openssl rand -hex 24 values
docker compose up -d
claude mcp add --transport http obsei http://localhost:8765/mcp \
  --header "Authorization: Bearer $OBSEI_API_TOKEN"
```

See [Docker Compose](/quickstart/#docker-compose).
