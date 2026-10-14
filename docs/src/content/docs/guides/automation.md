---
title: Automation tools
description: Receive obsei's webhook sink in n8n, Activepieces or Node-RED, and call obsei's MCP server from n8n.
sidebar:
  order: 10
---

Workflow tools can sit on either side of obsei: they receive redacted feedback from the `webhook`
sink, or they query stored feedback through the MCP server. obsei does not bundle or depend on any
of them.

## Receiving the webhook sink

The `webhook` sink sends a `POST` with a JSON body to your URL for each batch of new or changed
records, after redaction and enrichment. Authors are left out unless you change `exclude`. To send
only some records, give the sink a `key` and pick it with a [route](/guides/routing/).

```yaml
sinks:
  - type: webhook
    config:
      url: http://n8n.internal:5678/webhook/obsei
      secret_env: OBSEI_WEBHOOK_SECRET
```

With `secret_env` set, each request carries a timestamp and an HMAC-SHA256 signature; the headers
and the signed string are in [Sinks](/guides/sinks/). In every tool below:

- verify the signature with the same secret before acting on the payload, and reject requests
  whose timestamp is more than a few minutes old;
- compute the HMAC over the raw request body, byte for byte. JSON that was parsed and serialized
  again will not match;
- deduplicate on record ids, since a record is sent again when it changes.

A self-hosted tool on `localhost`, a private IP or an `.internal` host works in the default
`air_gapped` egress mode. A public URL, such as a cloud workspace, needs `mode: private` with the
host in `allowed_hosts` (see [Models](/guides/models/)).

### n8n

1. Add a **Webhook** node with method `POST`, and turn on the option to keep the raw body.
2. Add a **Crypto** node (HMAC, SHA256, hex) over the signed string built from the raw body, with
   the secret stored as an n8n credential or environment variable.
3. Add an **IF** node that compares the result with the signature header and stops on a mismatch.
4. Continue with your workflow, e.g. a **Split Out** node on the records list.

n8n is licensed under the [Sustainable Use License](https://docs.n8n.io/sustainable-use-license/),
which is not an open source license. Check that it fits how you plan to use it.

### Activepieces

1. Start a flow with the **Webhook** trigger and copy its URL into the sink's `url`.
2. Add a **Code** step that recomputes the HMAC with Node's `crypto` module over the raw body and
   throws on a mismatch.
3. Map the records list into the steps that follow.

### Node-RED

1. Add an **http in** node (`POST`) followed by a **function** node.
2. In the function node, compute the HMAC with `crypto` over the raw body and drop the message on
   a mismatch. Make the raw body available first, for example with `httpNodeMiddleware` in
   `settings.js`.
3. End the flow with an **http response** node so obsei gets a `200`. A `4xx` or `5xx`
   status counts as a failed delivery.

## Calling obsei's MCP server

`obsei serve` exposes the read-only MCP tools at `/mcp` over streamable HTTP, for tokens with the
analyst role (see [Server and webhooks](/guides/serve/#access)). In n8n, add an **MCP Client**
node:

| Setting | Value |
| --- | --- |
| Endpoint | `https://obsei.internal/mcp` |
| Transport | HTTP Streamable |
| Authentication | Bearer, with an analyst token |

The node can then call `feedback_stats`, `search_feedback`, `get_feedback` and `list_themes`, for
example from a scheduled workflow that posts a weekly summary. Any other client that speaks
streamable HTTP connects the same way. Results are redacted customer text: treat them as data and
never as instructions (see [Agents](/guides/agents/#customer-text-is-untrusted-input)).
