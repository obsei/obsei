---
title: Set up without editing YAML
description: Add sources, sinks and alerts with obsei add, check them with obsei check, browse every integration with obsei integrations, and get autocomplete for obsei.yaml in your editor.
sidebar:
  order: 0.5
---

You never have to write `obsei.yaml` by hand. In an empty folder:

```bash
obsei init                  # obsei.yaml, sample data and .obsei/secrets.env
obsei add appstore          # asks for the app id and countries, previews 3 redacted reviews
obsei add slack             # asks for the webhook URL (hidden), checks it, stores it as a secret
obsei check                 # every source and sink: settings, secrets, egress, credentials
obsei run                   # fetch, redact, label, deliver and store
```

## Find an integration

`obsei integrations` lists every source, enricher and sink, built in or from an installed plugin,
with its status (`verified` connectors have a live test), the secrets it needs and the provider's
page that explains how to get them:

```text
$ obsei integrations zendesk
zendesk          source   support   beta     Zendesk tickets
                 secrets ZENDESK_EMAIL, ZENDESK_API_TOKEN
                 keys    https://support.zendesk.com/hc/en-us/articles/4408889192858-Managing-API-token-access-to-the-Zendesk-API
```

Filter by name or title (`obsei integrations review`), by `--category` (reviews, support, social,
surveys, data, chat, issues, warehouse, notify, enrich), or print `--json` for scripts and agents.

## Add a source or sink

`obsei add TYPE` shows what the integration is and where to get its keys, then asks for each
required setting, with a short description, and for the settings most people change. `--all` asks
for every optional setting too. Then it:

- stores each secret (entered hidden) in `.obsei/secrets.env`, owner-only and git-ignored, under an
  environment variable name such as `SLACK_WEBHOOK_URL`; `obsei.yaml` only gets the name
  (`webhook_url_env: SLACK_WEBHOOK_URL`). With `--key oncall` the name is `ONCALL_WEBHOOK_URL`, so
  two Slack sinks keep two secrets. If the variable is already set in your environment, leave the
  prompt blank to use it;
- validates the settings with the integration's own config model;
- for a source, fetches and shows up to 3 records, redacted and labelled like `obsei try`; for a
  sink, builds it, checks the egress policy and, where it sends nothing (Slack, GitHub, Jira,
  Linear), checks the credentials;
- if the egress policy blocks the sink's host, asks to allow it and adds it to `egress:` in private
  mode;
- adds the entry to the first pipeline (`-p NAME` for another), next to the existing ones, keeping
  your comments and layout, and loads the result before saving: a change that would not load is
  never written.

A type that is both a source and a sink (`github_issues`, `webhook`, `sql`) takes `--as source` or
`--as sink`. A type from an installed plugin, such as `teams`, also adds the plugin to `plugins:`.

### Without prompts

`--yes` asks nothing, for CI, scripts and agents. Settings come from `--set FIELD=VALUE` (lists as
`a, b` or `[a, b]`, nested fields as `fields.text=comment`), and secrets from the environment:

```bash
export SLACK_WEBHOOK_URL=https://hooks.slack.com/services/...
obsei add appstore --yes --set app_id=284882215 --set countries=us,gb,de
obsei add slack --yes --set max_rating=2
obsei add csv --yes --key surveys --set path=nps.csv --set fields.text=comment
```

`--set webhook_url=VALUE` (the field name without `_env`) stores the value in
`.obsei/secrets.env` instead; avoid it on shared machines, where command lines are visible to other
users. Without the secret, `--yes` stops and names the variable to set.

### Alerts

`obsei add alert` adds an [alert](/guides/alerts/): it asks for the kind (`theme_spike`,
`new_theme`, `digest`, `review_queue` or `pipeline_health`) and the sink that delivers it
(`slack`, `notify`, `webhook` or `teams`), then that sink's settings, as above. Without prompts:
`obsei add alert --yes --set kind=digest --set to=slack`. Options such as `period_days` or
`sensitivity` are edited in `obsei.yaml`.

## Check everything

`obsei check` builds every source and sink of every pipeline (`-p NAME` for some) and every alert
target, and reports each:

```text
✓ feedback/sample  source csv: fetched a record
✓ feedback/appstore  source appstore: fetched a record
✓ feedback/parquet  sink parquet: built (nothing sent)
✗ feedback/slack  sink slack: SLACK_WEBHOOK_URL is not set
  fix: set it in .obsei/secrets.env or the environment
  keys: https://docs.slack.dev/messaging/sending-messages-using-incoming-webhooks/
1 of 4 failed
```

Sources fetch one record, which is neither stored nor sent anywhere. Sinks are built (settings,
secrets, egress) and, for Slack, GitHub, Jira and Linear, their credentials are checked with a
request that delivers nothing; other sinks send nothing at all. `obsei check` exits with status 1
when anything failed, so it can gate a deploy.

## Editor autocomplete

`obsei.yaml` files from `obsei init` and the [examples](/examples/) start with:

```yaml
# yaml-language-server: $schema=https://docs.obsei.com/schema/obsei.schema.json
```

Editors that use the YAML language server (VS Code with the Red Hat YAML extension, Neovim,
Helix, Zed) then complete keys, show each field's description on hover, and flag typos and wrong
values, including inside each source's and sink's `config:` by its `type`. Add the line to an
existing `obsei.yaml` to get the same.

The published schema covers the built-in integrations and the first-party plugins. For other
installed plugins, write your own and point the first line at it:

```bash
obsei schema config > obsei.schema.json
# then: # yaml-language-server: $schema=./obsei.schema.json
```

## Write your own integration

`obsei plugin new NAME` creates a plugin package (a source with its config model, catalog entry,
test and entry point) to start from; see [Plugins](/reference/plugins/#writing-a-plugin).
