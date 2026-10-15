---
title: Server and webhooks
description: Run obsei as a service with webhook intake and remote MCP.
sidebar:
  order: 7
---

```bash
export OBSEI_API_TOKEN="$(openssl rand -hex 32)"
obsei serve --host 0.0.0.0 --port 8765
```

| Path | Auth | Purpose |
| --- | --- | --- |
| `GET /healthz` | none | liveness: `{"status": "ok"}`, or `503 {"status": "degraded"}` if the scheduler stopped |
| `POST /ingest/{pipeline}/{source}` | Standard Webhooks signature | push feedback into a `webhook` source (1 MB max) |
| `POST /slack/commands` | Slack request signature | the `/obsei` slash command (404 without `SLACK_SIGNING_SECRET`) |
| `GET /` | none | redirects to `/studio/` |
| `GET /studio/` | none (static files) | [Studio](/guides/studio/); its data comes from `/api/*` with the caller's token |
| `GET /api/snapshot` | viewer | k-anonymous overview, themes and knowledge graph, without quotes |
| `GET /api/themes/{id}` | analyst | redacted evidence for one theme (empty below `k_anonymity`) |
| `POST /api/ask` | analyst | `{"question": "..."}` returns `{"answer": "...", "grounded": 0.93, "possibly_unsupported": false}` with record-id citations; `grounded` is null without `ask_judge` |
| `/mcp` | analyst | MCP over streamable HTTP |
| `GET /api/runs` | admin | schedule and last run of each scheduled pipeline, with errors and warnings |
| `GET /api/deliveries` | admin | the latest 100 [webhook deliveries](/guides/sinks/#webhooks): event id, sink, host, attempts, status, error |
| `GET /api/approvals` | admin | the latest 100 [agent proposals](/guides/mcp/#approvals) and their status |
| `POST /api/approvals/{id}/approve` | admin | open the proposed issue (once) and return the approval |
| `POST /api/approvals/{id}/reject` | admin | optional `{"reason": "..."}`; nothing is sent |

Any other path needs admin. Roles are checked only when `OBSEI_API_TOKEN` or `access` is
configured; without either, every path is open, which `obsei serve` allows only on a loopback
address (`127.0.0.1`, `::1`, `localhost`). Binding to any other address requires
`OBSEI_API_TOKEN` or `access`. Every token (`OBSEI_API_TOKEN` and each user's `token_env`) must
be at least 16 characters. Pipelines with `every_minutes` run on
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

Sign requests per [Standard Webhooks](https://www.standardwebhooks.com/), as the
[webhook sink](/guides/sinks/#webhooks) and its libraries do: `webhook-id` (any unique id),
`webhook-timestamp` (Unix seconds) and `webhook-signature: v1,<base64 HMAC-SHA256 of
"{webhook-id}.{webhook-timestamp}.{body}">`. Several space-separated signatures are accepted, so
you can rotate secrets. A `whsec_` secret is base64-decoded; any other value is used as its raw
bytes. Requests more than `max_age_seconds` (default 300) away from the server's clock are
refused, so a captured request cannot be replayed later. Senders that sign the body only, such as
GitHub (`X-Hub-Signature-256: sha256=<hex HMAC of the body>`), need `require_timestamp: false` on
the source, which gives up that protection. Map `id` and `created_at` so that redeliveries are
recognised as unchanged.

```bash
id=msg_$(openssl rand -hex 12) ts=$(date +%s)   # with a raw (non-whsec_) secret
sig=$({ printf '%s.%s.' "$id" "$ts"; cat body.json; } | openssl dgst -sha256 -hmac "$TICKETS_HOOK_SECRET" -binary | base64)
curl -X POST https://obsei.internal/ingest/support/tickets --data-binary @body.json \
  -H "webhook-id: $id" -H "webhook-timestamp: $ts" -H "webhook-signature: v1,$sig"
```

Earlier release candidates expected `X-Obsei-Timestamp` and `X-Obsei-Signature-256`; senders now
use the headers above.

A request is accepted as a whole or not at all: an invalid item returns `400` naming the item.
Items without text are skipped, and the reply counts them:
`{"received": 3, "skipped": 1, "stored": 2}`.

## Access

`OBSEI_API_TOKEN` is an admin token. For teams, give each group its own token and role, or put
obsei behind your SSO proxy (oauth2-proxy, Pomerium, Cloudflare Access) and map groups to roles:

| Role | Can use |
| --- | --- |
| viewer | Studio aggregates and themes (`/api/snapshot`) |
| analyst | also redacted evidence, Ask and MCP (`/api/themes/*`, `/api/ask`, `/mcp`) |
| admin | also pipeline run status, webhook deliveries and approvals (`/api/runs`, `/api/deliveries`, `/api/approvals`) |

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
Ask, MCP and admin request is written to the audit log (`obsei audit`) with the user and path.
Approvals over HTTP need a token or SSO proxy, even on a loopback address; without one, use
`obsei approvals`. Give agents analyst tokens, never admin ones.

## Allowed hosts

Against DNS rebinding, every route answers only to `localhost`, `127.0.0.1`, `[::1]`, the
`--host` address and the names in `access.allowed_hosts`; other `Host` or `Origin` headers get
421. When bound to `0.0.0.0` without `allowed_hosts`, any host is accepted (a token or SSO proxy
is required then), so list your public names there:

```yaml
access:
  allowed_hosts: [voc.example.com, "*.corp.example"]
```
