---
title: Alerts
description: Theme spikes, new themes, weekly digests, the review queue and pipeline health, sent to Slack, email, Teams or a webhook.
sidebar:
  order: 5.5
---

Sinks deliver records one by one as they arrive. Alerts work on aggregates instead: a theme that
grows faster than usual, a theme that appeared this week, a weekly digest, a review queue that
needs a human, or a pipeline that stopped working. obsei keeps alert state in the store, so each
alert fires once per cooldown instead of on every run.

```yaml
alerts:
  - name: spikes
    kind: theme_spike
    owner: "@mobile-oncall"     # optional, shown in the message
    sensitivity: 2.0            # z-score (default 2.0)
    min_count: 5                # records this week (default 5)
    cooldown_hours: 168         # default for spikes: once a week per theme
    to:
      - type: slack
        config: {webhook_url_env: SLACK_ALERTS_URL}
```

| `kind` | Fires when | Key | Options |
| --- | --- | --- | --- |
| `theme_spike` | a theme's last 7 days are well above its usual week | theme id | `sensitivity`, `min_count`, `quotes` |
| `new_theme` | a theme whose records all arrived in the last 7 days reaches `k_anonymity` people; once per theme | theme id | `quotes` |
| `digest` | every `period_days` (default 7): record count and the `top` (default 5) themes of the period | `digest` | `period_days`, `top` |
| `review_queue` | at least `min_pending` (default 10) records from the last 7 days were marked for review | `review` | `min_pending` |
| `pipeline_health` | a run fails; with `stale_hours`, also a source that fetched nothing for that long | pipeline, or `pipeline/source` | `stale_hours` |

`to` lists the sinks that deliver the alert, written like pipeline sinks (`type`, `config` and an
optional `key`, needed when two have the same type). They are separate from pipeline sinks, so an
alerts channel never receives individual records. `webhook`, `slack`, `notify` and the `teams`
plugin deliver alerts; any other sink type is a configuration error. Sink options that filter
records (`when`, `max_rating`, ...) do not apply to alerts.

## When alerts are checked

- `obsei alerts check` checks every alert now; run it from cron, or add `--dry-run` to see what
  would fire without sending or recording anything.
- `obsei run` and `obsei themes` check alerts after they finish.
- `obsei serve` checks them after each scheduled run (and after `themes.auto` updates themes).

Theme alerts read themes as they were last updated, so keep themes current with `themes.auto: true`
or `obsei themes`.

## Spike statistics

Themes keep weekly counts for the last 8 weeks. A theme spikes when this week (the last 7 days)
stands out from the 7 weeks before:

```text
z = (this week - mean of the 7 weeks before) / max(standard deviation, 1)
```

It fires when `z >= sensitivity`, this week has at least `min_count` records, and the theme is
also rising as Studio shows it: at least 3 records and at least double the week before. The
standard deviation is never taken below 1, so for a theme with a flat history `z` is simply how many
records above its usual week it is. The rising rule is computed by the server and returned as `rising` by Studio, the
MCP `list_themes` tool and `obsei themes`.

Low volume means few alerts. With 20 records a week, a theme rarely reaches `min_count`, and that
is deliberate: a jump from 1 to 3 is noise. Lower `min_count` or `sensitivity` only if your volume
is steady.

## Privacy

Alerts only read k-anonymous theme summaries: a theme from fewer than `themes.k_anonymity` people
(default 5) is never reported, however fast it grows. Theme alerts carry up to `quotes` (default 3,
`0` for none) representative quotes, as stored, so redacted, and never authors or pseudonyms.
Digests, review queue and health alerts carry counts only.

## Cooldown, snooze and ack

Each alert fires at most once per key per `cooldown_hours` while its condition holds. The default
is 168 (a week, the spike window) for `theme_spike`, so a spike that lasts all week alerts once,
and 24 for the review queue and pipeline health. A digest fires once per `period_days` and a new
theme once ever.

```bash
obsei alerts list                                  # last fired, snoozed and acked keys
obsei alerts snooze spikes thm_3f2a9c1b --hours 72  # silence one key for a while
obsei alerts ack spikes thm_3f2a9c1b --by ana       # acknowledged: silent for 7 days
```

An ack silences that key for 7 days, the length of the spike window, and records who
acknowledged it. If the theme still spikes after that, the alert fires again.

## Examples

A weekly digest by email through [Apprise](/guides/sinks/#notifications):

```yaml
alerts:
  - name: weekly
    kind: digest
    period_days: 7
    top: 5
    to:
      - type: notify
        config: {urls_env: DIGEST_EMAIL}   # mailtos://user:app_password@gmail.com?to=voc@acme.com
```

The review queue to Microsoft Teams with the [`teams` plugin](/reference/plugins/) (`plugins: [teams]`):

```yaml
alerts:
  - name: review
    kind: review_queue
    min_pending: 10
    owner: Support leads
    to:
      - type: teams
        config: {webhook_url_env: TEAMS_REVIEW_URL}
```

Everything to n8n through a signed [webhook](/guides/sinks/#webhooks):

```yaml
alerts:
  - name: new-themes
    kind: new_theme
    to: [{type: webhook, config: {url: "https://n8n.acme.com/webhook/obsei", secret_env: N8N_SECRET}}]
  - name: health
    kind: pipeline_health
    stale_hours: 48
    to: [{type: webhook, config: {url: "https://n8n.acme.com/webhook/obsei", secret_env: N8N_SECRET}}]
```

Webhook alerts are CloudEvents like record batches, with these `type`s, and are logged in the
`deliveries` table with pipeline `alerts/<name>`:

| `kind` | Event `type` |
| --- | --- |
| `theme_spike` | `obsei.theme.spiking` |
| `new_theme` | `obsei.theme.new` |
| `digest` | `obsei.digest` |
| `review_queue` | `obsei.review.pending` |
| `pipeline_health` | `obsei.pipeline.failed` |

`data` holds the alert:

```json
{
  "alert": "spikes",
  "kind": "theme_spike",
  "key": "thm_3f2a9c1b",
  "title": "Theme spiking: Can't log in",
  "lines": ["15 records in the last 7 days against 2.4 a week over the 7 weeks before (z = 11.2)", "Sources: appstore 9, playstore 6", "Owner: @mobile-oncall"],
  "count": 15,
  "baseline": 2.43,
  "theme": "thm_3f2a9c1b",
  "quotes": ["Since the update I cannot log in, it says <EMAIL> is unknown"],
  "owner": "@mobile-oncall"
}
```
