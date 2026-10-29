---
title: Sources
description: Built-in sources and their configuration.
sidebar:
  order: 1
---

Add any of these with `obsei add TYPE`, which asks for the settings and keys and previews a few
records; `obsei integrations` lists each one's secrets and where to get them
([Set up without editing YAML](/guides/setup/)).

| Type | What | Auth | Status |
| --- | --- | --- | --- |
| <span class="i i-file-spreadsheet"></span> `csv` | Survey exports, ticket dumps, NPS verbatims | none | verified |
| <span class="i i-file-json"></span> `jsonl` | Ticket dumps and other JSON Lines exports | none | beta |
| <span class="i i-globe"></span> `rest` | Any JSON API, with page, offset, link, next-URL or cursor pagination | bearer or headers from env | beta |
| <span class="i i-webhook"></span> `webhook` | Pushed feedback via `obsei serve` (`POST /ingest/{pipeline}/{key}`) | Standard Webhooks signature | beta |
| <span class="i i-smartphone"></span> `appstore` | Apple public review feed, any list of countries | none | verified |
| <span class="i i-smartphone"></span> `appstoreconnect` | Your apps' reviews in every territory (official API) | `.p8` key, `obsei[apple]` | beta |
| <span class="i i-play"></span> `playstore` | Your apps' reviews (official Android Publisher API) | service account, `obsei[google]` | beta |
| <span class="i i-github"></span> `github_issues` | Issues and comments, GitHub or GitHub Enterprise; issue-template headings, checklists, HTML comments and collapsed attachments are dropped | `GITHUB_TOKEN` (optional) | verified |
| <span class="i i-ycombinator"></span> `hackernews` | Stories and comments matching a query | none | verified |
| <span class="i i-bluesky"></span> `bluesky` | Posts matching a query, optionally by language | none or app password | beta |
| <span class="i i-video"></span> `youtube` | Comments on videos or a whole channel | `YOUTUBE_API_KEY` | beta |
| <span class="i i-rss"></span> `rss` | RSS 2.0 and Atom: forums, status pages, review sites | none | verified |
| <span class="i i-reddit"></span> `reddit` ([plugin](#reddit-plugin), from Git) | Subreddit posts, comments and searches via RSS | none | beta |
| <span class="i i-clipboard-list"></span> `typeform` ([plugin](/reference/plugins/), from Git) | Completed survey responses, incremental | personal access token | beta |
| <span class="i i-database"></span> `sql` | Any SQLAlchemy database or warehouse, incremental by a cursor column | URL in env, `obsei[sql]` | beta |
| <span class="i i-folder-input"></span> `filedrop` | New or changed CSV, JSON Lines and JSON files in a folder (SFTP drop, mounted bucket) | none | beta |
| <span class="i i-mail"></span> `imap` | Feedback mailboxes | username and password in env | beta |
| <span class="i i-modelcontextprotocol"></span> `mcp` | A tool on any MCP server (stdio command or HTTP URL) | none | beta |
| <span class="i i-zendesk"></span> `zendesk` | Tickets, incremental export | email and API token | beta |
| <span class="i i-headset"></span> `freshdesk` | Tickets updated since the last run | API key | beta |
| <span class="i i-intercom"></span> `intercom` | Conversations, in the US, EU or AU data region | access token | beta |
| <span class="i i-phone-call"></span> `gong` | Call transcripts, customer speech only | access key and secret | beta |

`verified` means a live test in
[`packages/obsei/tests/live`](https://github.com/obsei/obsei/tree/master/packages/obsei/tests/live)
exercises the connector end to end against the real service or data; `beta` connectors are
covered by mocked tests only.

## Field mapping

`csv`, `jsonl`, `filedrop`, `sql`, `rest`, `webhook` and `mcp` map fields with dotted paths:

```yaml
fields:
  text: [subject, body]       # several fields are joined
  id: ticket.id
  created_at: ticket.created  # ISO 8601, RFC 2822 or epoch seconds
  rating: score
  author: requester.email     # pseudonymised, never stored in clear
  lang: locale
  url: link
  context: [plan, region]     # kept as string metadata
```

## Recipes with the REST source

`rest` reads any JSON API. Set `items_path` to the list of items, map `fields`, and pick the
pagination the API uses: `page` or `offset` (with `page_param`, `page_size_param`), `link`
(the `Link: rel="next"` header), `next_url` or `cursor` (both read `next_path`; `cursor` sends the
token as `cursor_param`). Credentials come from `bearer_token_env` or `secret_headers` and are only
sent to the configured host, never to hosts named by pagination.

APIs that return HTML (Mastodon, forums, some helpdesks) can set `text_format: html`: the mapped
`text` fields are converted to plain text (tags removed, entities decoded, paragraphs kept as line
breaks) before redaction. The default is `plain`, which keeps the text as returned.

```yaml
- key: mastodon
  type: rest
  config:
    url: https://mastodon.social/api/v1/timelines/tag/yourproduct
    params: {limit: 40}
    pagination: link
    max_pages: 5
    text_format: html
    fields: {text: content, id: id, created_at: created_at, author: account.acct, lang: language, url: url}
```

Complete recipes:

| API | Example |
| --- | --- |
| Trustpilot business reviews (API key header, page paging) | [`trustpilot-rest.yaml`](https://github.com/obsei/obsei/blob/master/examples/trustpilot-rest.yaml) |
| HubSpot tickets (cursor on `paging.next.after`) and ServiceNow incidents (`sysparm_offset`) | [`crm-and-itsm-rest.yaml`](https://github.com/obsei/obsei/blob/master/examples/crm-and-itsm-rest.yaml) |
| Mastodon hashtag timeline (`Link` header, HTML) | [`social-listening.yaml`](https://github.com/obsei/obsei/blob/master/examples/social-listening.yaml) |
| Atlassian Marketplace app reviews (public API, `next_url` on `_links.next.href`) | [`atlassian-marketplace-reviews.yaml`](https://github.com/obsei/obsei/blob/master/examples/atlassian-marketplace-reviews.yaml) |
| Google Business Profile reviews of your locations (OAuth bearer token, `cursor` on `nextPageToken`; beta) | [`google-business-reviews.yaml`](https://github.com/obsei/obsei/blob/master/examples/google-business-reviews.yaml) |
| Confluence Cloud pages of a space (basic auth header, `Link` header, HTML) | [`confluence-pages.yaml`](https://github.com/obsei/obsei/blob/master/examples/confluence-pages.yaml) |
| WordPress.org plugin reviews (the `rss` source on the plugin's review feed) | [`wordpress-plugin-reviews.yaml`](https://github.com/obsei/obsei/blob/master/examples/wordpress-plugin-reviews.yaml) |

More complete setups are on the [Examples](/examples/) page.

## Reddit plugin

`reddit` is a first-party plugin, installed from Git rather than PyPI. Install it, then allow it in
`obsei.yaml` with `plugins: [reddit]`:

```bash
pip install "obsei-reddit @ git+https://github.com/obsei/obsei#subdirectory=plugins/obsei-reddit"
# or, with uv tool:
uv tool install "obsei>=1.0" \
  --with "obsei-reddit @ git+https://github.com/obsei/obsei#subdirectory=plugins/obsei-reddit"
```

## App Store feeds

`appstore` reads Apple's public review feed, which needs no key but is unofficial. Since mid-2026
Apple's CDN often serves one spelling of the feed empty while another has the reviews, so obsei
tries four spellings, as XML and then JSON, before it treats a country as empty. Apple now returns
only the latest 50 reviews per country (later pages are empty), so run it often enough that new
reviews don't scroll past. For your own apps, `appstoreconnect` uses the official API and covers
every review.

## Global coverage

Use the country and language filters to follow every market you serve: `appstore.countries`
takes ISO 3166 alpha-2 codes (`us`, `br`, `jp`, `in`, `ng`, ...), `appstoreconnect.territories`
takes alpha-3 codes (`USA`, `BRA`, `JPN`, `IND`, `NGA`), and `bluesky.lang` filters by language.
Records keep their original language; enrichers never translate the stored text.
