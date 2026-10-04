---
title: Server and webhooks
description: Run obsei as a service with webhook intake and remote MCP.
sidebar:
  order: 6
---

```bash
export OBSEI_API_TOKEN="$(openssl rand -hex 32)"
obsei serve --host 0.0.0.0 --port 8765
```

| Path | Auth | Purpose |
| --- | --- | --- |
| `GET /healthz` | none | liveness: `{"status": "ok"}` |
| `POST /ingest/{pipeline}/{source}` | HMAC-SHA256 signature | push feedback into a `webhook` source (1 MB max) |
| `POST /slack/commands` | Slack request signature | the `/obsei` slash command (404 without `SLACK_SIGNING_SECRET`) |
| `GET /studio/` | none (static files) | [Studio](/guides/studio/); its data comes from `/api/*` with the caller's token |
| `GET /api/snapshot` | viewer | k-anonymous overview, themes and knowledge graph, without quotes |
| `GET /api/themes/{id}` | analyst | redacted evidence for one theme (empty below `k_anonymity`) |
| `POST /api/ask` | analyst | `{"question": "..."}` returns `{"answer": "..."}` with record-id citations |
| `/mcp` | analyst | MCP over streamable HTTP |
| `GET /api/runs` | admin | schedule and last run of each scheduled pipeline |

Any other path needs admin. Roles are checked only when `OBSEI_API_TOKEN` or `access` is
configured; without either, every path is open, which `obsei serve` allows only on a loopback
address (`127.0.0.1`, `::1`, `localhost`). Binding to any other address requires
`OBSEI_API_TOKEN` or `access`. Pipelines with `every_minutes` run on
their schedule inside the server (see [Configuration](/configuration/#scheduling)).

## Sending feedback

```yaml
sources:
  - key: tickets
    type: webhook
    config:
      secret_env: TICKETS_HOOK_SECRET
      items_path: tickets
      fields: {id: id, created_at: created_at, text: [subject, body], lang: locale}
```

Sign the raw body: `X-Obsei-Signature-256: sha256=<hex HMAC of body>`. GitHub-style
`X-Hub-Signature-256` is accepted too. Map `id` and `created_at` so that redeliveries are
recognised as unchanged.

## Access

`OBSEI_API_TOKEN` is an admin token. For teams, give each group its own token and role, or put
obsei behind your SSO proxy (oauth2-proxy, Pomerium, Cloudflare Access) and map groups to roles:

| Role | Can use |
| --- | --- |
| viewer | Studio aggregates and themes (`/api/snapshot`) |
| analyst | also redacted evidence, Ask and MCP (`/api/themes/*`, `/api/ask`, `/mcp`) |
| admin | also pipeline run status (`/api/runs`) |

```yaml
access:
  users:
    - {name: support-leads, token_env: OBSEI_TOKEN_SUPPORT, role: viewer}
    - {name: voc-team, token_env: OBSEI_TOKEN_VOC, role: analyst}
  trusted_proxy:
    secret_env: OBSEI_PROXY_SECRET     # the proxy sends it in X-Obsei-Proxy-Secret
    user_header: X-Forwarded-Email
    groups_header: X-Forwarded-Groups
    roles: {analyst: [voc], admin: [platform]}
    default_role: viewer
```

Requests without the proxy secret are refused, so the proxy cannot be bypassed. Every evidence,
Ask and MCP request is written to the audit log (`obsei audit`) with the user and path.
