---
title: Server and webhooks
description: Run obsei as a service with webhook intake and remote MCP.
---

```bash
export OBSEI_API_TOKEN="$(openssl rand -hex 32)"
obsei serve --host 0.0.0.0 --port 8765
```

| Path | Auth | Purpose |
| --- | --- | --- |
| `GET /healthz` | none | liveness |
| `POST /ingest/{pipeline}/{source}` | HMAC-SHA256 signature | push feedback into a `webhook` source |
| `/mcp` | bearer token | MCP over streamable HTTP |
| `GET /api/runs` | bearer token | last run of each scheduled pipeline |

Binding to a non-loopback address requires `OBSEI_API_TOKEN`. Pipelines with `every_minutes` run on
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
