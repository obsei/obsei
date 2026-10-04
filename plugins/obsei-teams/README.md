# obsei-teams

Posts matching feedback to a Microsoft Teams channel as an Adaptive Card, through a Power
Automate **Workflows** webhook (Microsoft retired the Office 365 connector incoming webhooks).

Install it from PyPI once published:

```bash
pip install obsei-teams
```

Until then, install it from Git:

```bash
pip install "obsei-teams @ git+https://github.com/obsei/obsei#subdirectory=plugins/obsei-teams"
```

In Teams, open the channel's **Workflows** and choose the template *Post to a channel when a
webhook request is received*. Copy the URL it creates into an environment variable; it carries
a signature, so treat it as a secret and never put it in `obsei.yaml`.

```yaml
plugins: [teams]
egress:
  mode: private
  allowed_hosts: [logic.azure.com, environment.api.powerplatform.com]
pipelines:
  - name: alerts
    sources:
      - key: ios
        type: appstore
        config: {app_id: "284882215"}
    enrichers:
      - type: classify
        config: {llm: default}
    sinks:
      - type: teams
        config:
          title: Negative app reviews
          when: {classify.sentiment: [negative]}
          max_rating: 2
```

| Field | Default | Meaning |
|---|---|---|
| `webhook_url_env` | `TEAMS_WEBHOOK_URL` | Environment variable holding the Workflows URL. |
| `title` | `New customer feedback` | Card heading. |
| `when` | all records | Enrichment labels to match, as in the `slack` sink. |
| `max_rating` | none | Only records rated at or below this. |
| `max_records` | 10 | Records per card (up to 25); the card counts the rest. |
| `max_text` | 600 | Characters of feedback shown per record. |

Each batch becomes at most one message. A record shows its source, rating, sentiment and intent
(when the `classify` enricher ran), its redacted text as plain text (customer text cannot add
links or formatting) and an *Open* button for http(s) links. Authors are never sent.

The webhook hosts are public (`*.logic.azure.com`, or `*.environment.api.powerplatform.com` for
newer workflows), so obsei's default air-gapped egress policy blocks them. Allow them with
`OBSEI_EGRESS_MODE=private` and `OBSEI_EGRESS_ALLOW=logic.azure.com,environment.api.powerplatform.com`
or the `egress` block above. Every request, redirects included, is checked against the policy.
