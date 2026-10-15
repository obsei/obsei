---
title: Sinks
description: Where obsei delivers feedback.
sidebar:
  order: 2
---

Sinks receive only new or changed records, after redaction and enrichment, and are not called
when a batch has none for them. Outbound sinks are checked against the egress policy when the
pipeline starts; `sql` checks the database host in its URL (BigQuery and Snowflake accounts count
as their cloud hosts, SQLite files as local).

Add one with `obsei add TYPE`: it asks for the settings, keeps the secret in
`.obsei/secrets.env`, checks the egress policy and, for Slack, GitHub, Jira and Linear, the
credentials, without sending anything ([Set up without editing YAML](/guides/setup/)).

| Type | What | Idempotency | Status |
| --- | --- | --- | --- |
| <span class="i i-webhook"></span> `webhook` | One CloudEvents JSON event per batch, signed per [Standard Webhooks](https://www.standardwebhooks.com/), retried; authors omitted by default | `webhook-id` per event, record ids in the payload | beta |
| <span class="i i-message-square"></span> `slack` | Messages for matching feedback, capped per run | at-least-once | verified |
| <span class="i i-bell"></span> `notify` | One summary per batch to Telegram, Discord, email, Teams and 100+ services via [Apprise](https://github.com/caronc/apprise) (`obsei[notify]`) | at-least-once | beta |
| <span class="i i-github"></span> `github_issues` | One issue per matching record | hidden marker, searched before creating | beta |
| <span class="i i-jira"></span> `jira` | One issue per matching record (Cloud with ADF, or Data Center) | `obsei-rec_...` label | beta |
| <span class="i i-linear"></span> `linear` | One issue per matching record | marker in the description | verified |
| <span class="i i-apacheparquet"></span> `parquet` | Parquet files for notebooks and lakes | file named by batch content | beta |
| <span class="i i-database"></span> `sql` | Upsert into a table in any SQLAlchemy database or warehouse | delete and insert by id | beta |
| <span class="i i-users"></span> `teams` ([plugin](/reference/plugins/), `pip install obsei-teams`) | An Adaptive Card per matching record in a Microsoft Teams channel | at-least-once | beta |

`verified` means a live test in
[`packages/obsei/tests/live`](https://github.com/obsei/obsei/tree/master/packages/obsei/tests/live)
exercises the connector end to end against the real service or data; `beta` connectors are
covered by mocked tests only.

## Filters

Issue and chat sinks take `when` (labels from enrichers) and `max_rating`:

```yaml
- type: jira
  config:
    base_url: https://acme.atlassian.net
    project_key: APP
    when: {classify.intent: [bug]}
    max_rating: 2
```

`when` reads nested fields and yes/no values too, e.g.
`{classify.fields.urgency: [today, right now]}` or `{filter.match: ["false"]}`. Instead of a list,
a condition can test what a decision model stores: `{is: bug, min_confidence: 0.8}`,
`{gte: today}` on a score field, `{min_probability: 0.7}` on a yes/no field, and `review: false`
to skip records flagged for review. See [Routing](/guides/routing/#conditions) for every condition.

## Routes

`when` filters fan out: each sink checks every record. To send each record to one set of sinks,
give sinks a `key` and add ordered `route:` rules to the pipeline; the first match wins, with a
`default` and a `review` shortcut for records still flagged after the fallback:

```yaml
sinks:
  - {key: jira, type: jira, config: {base_url: https://acme.atlassian.net, project_key: SUP, when: {}}}
  - {key: oncall, type: slack, config: {webhook_url_env: ONCALL_SLACK_WEBHOOK_URL}}
  - {key: lake, type: parquet, config: {directory: lake}}
route:
  - name: urgent-bugs
    when: {classify.intent: [bug], classify.fields.urgency: {gte: today}}
    sinks: [jira, oncall]
  - default: [lake]
```

Sinks no route names still receive every record through their own `when`. The
[Routing](/guides/routing/) guide covers the rules, the stored `route` enrichment and a full
example.

## Webhooks

```yaml
- key: hub
  type: webhook
  config:
    url: https://feedback-hub.internal/obsei
    secret_env: FEEDBACK_HUB_SECRET
    headers: {X-Team: voc}          # optional extra headers
    exclude: [author]               # the default: pseudonyms are never forwarded
```

Each batch is one event, a [CloudEvents 1.0](https://cloudevents.io/) JSON envelope; `source` is
`obsei/<pipeline>/<sink key>`:

```json
{"specversion": "1.0", "id": "evt_4f0c…", "type": "obsei.records.routed",
 "source": "obsei/support/hub", "time": "2026-10-15T09:00:00.123456+00:00",
 "datacontenttype": "application/json", "data": {"records": [{"id": "rec_…", "text": "…"}]}}
```

The headers follow [Standard Webhooks](https://www.standardwebhooks.com/):

| Header | Value |
| --- | --- |
| `webhook-id` | the event `id`; the same on every retry of the event, so use it to skip repeats |
| `webhook-timestamp` | Unix seconds of the attempt |
| `webhook-signature` | with `secret_env`: `v1,<base64 HMAC-SHA256 of "{webhook-id}.{webhook-timestamp}.{body}">` |

Use a `whsec_` secret, `whsec_` followed by 24 to 64 random bytes in base64
(`echo "whsec_$(openssl rand -base64 32)"`), and the standardwebhooks libraries take it as is. Any
other value is used as its raw UTF-8 bytes; pass it to the libraries as bytes (Python
`Webhook(secret.encode())`, JavaScript `new Webhook(secret, {format: "raw"})`).

```python
from standardwebhooks import Webhook  # pip install standardwebhooks

event = Webhook(os.environ["FEEDBACK_HUB_SECRET"]).verify(body, headers)  # raw body bytes
for record in event["data"]["records"]:
    ...
```

```js
import { Webhook } from "standardwebhooks"; // npm install standardwebhooks

const event = new Webhook(process.env.FEEDBACK_HUB_SECRET).verify(rawBody, req.headers);
```

Both refuse events more than 5 minutes old. Automation tools take these events too: point an n8n
Webhook node or a Zapier "Catch Hook" at the URL and read `data.records`.

Connection errors, `429` and `5xx` replies are retried up to 3 attempts in all, waiting 1 s then
2 s (or the reply's `Retry-After`, up to 30 s). Other `4xx` replies fail at once. If the last
attempt fails, the run fails: the batch is not stored and the next run sends it again as a new
event with a new `webhook-id`, so receivers should also deduplicate by record `id`.

Each event's final outcome (event id, pipeline, sink, host, type, attempts, status, error) is kept
in the store's `deliveries` table; admins read the latest 100 at `GET /api/deliveries` on
[`obsei serve`](/guides/serve/).

## Notifications

`notify` sends one short message per batch through [Apprise](https://github.com/caronc/apprise)
(`pip install 'obsei[notify]'`): how many records matched, then up to `max_items` (default 5)
redacted first lines with links. It takes `when` and `max_rating` like the issue sinks. The
Apprise URLs hold tokens, so they are read from the environment variable `urls_env` names
(default `APPRISE_URLS`); separate several with spaces or commas.

```yaml
- type: notify
  config:
    urls_env: VOC_ALERT_URLS
    when: {classify.intent: [bug, churn_risk]}
    max_rating: 2
```

| Service | `VOC_ALERT_URLS` |
| --- | --- |
| Telegram | `tgram://{bot_token}/{chat_id}` |
| Discord | `discord://{webhook_id}/{webhook_token}` |
| Email | `mailtos://{user}:{app_password}@gmail.com?to=voc@acme.com` |
| Microsoft Teams (Power Automate workflow) | `workflows://{host}:{port}/{workflow}/{signature}` |

The [Apprise wiki](https://github.com/caronc/apprise/wiki) lists every service. Each target must
pass the egress policy: obsei checks the service's API host (`api.telegram.org`, `discord.com`),
the SMTP server of email, and the host in the URL for self-hosted services (`json://`, `ntfys://`
on your server, Matrix). A service whose host obsei cannot tell, such as `ntfy://` on ntfy.sh, needs
hybrid mode. Apprise makes its own connections, so they do not go through obsei's HTTP client.
