---
title: Sources
description: Built-in sources and their configuration.
sidebar:
  order: 1
---

| Type | What | Auth |
| --- | --- | --- |
| `csv`, `jsonl` | Survey exports, ticket dumps, NPS verbatims | none |
| `rest` | Any JSON API, with page, offset, link, next-URL or cursor pagination | bearer or headers from env |
| `webhook` | Pushed feedback via `obsei serve` (`POST /ingest/{pipeline}/{key}`) | HMAC-SHA256 |
| `appstore` | Apple public review feed, any list of countries | none |
| `appstoreconnect` | Your apps' reviews in every territory (official API) | `.p8` key, `obsei[apple]` |
| `playstore` | Your apps' reviews (official Android Publisher API) | service account, `obsei[google]` |
| `github_issues` | Issues and comments, GitHub or GitHub Enterprise | `GITHUB_TOKEN` (optional) |
| `hackernews` | Stories and comments matching a query | none |
| `bluesky` | Posts matching a query, optionally by language | none or app password |
| `youtube` | Comments on videos or a whole channel | `YOUTUBE_API_KEY` |
| `rss` | RSS 2.0 and Atom: forums, status pages, review sites | none |
| `reddit` (community plugin, [not on PyPI](#reddit-plugin)) | Subreddit posts, comments and searches via RSS | none |
| `sql` | Any SQLAlchemy database or warehouse, incremental by a cursor column | URL in env, `obsei[sql]` |
| `filedrop` | New or changed CSV, JSON Lines and JSON files in a folder (SFTP drop, mounted bucket) | none |
| `imap` | Feedback mailboxes | username and password in env |
| `mcp` | A tool on any MCP server (stdio command or HTTP URL) | `obsei[mcp]` |
| `zendesk` | Tickets, incremental export | email and API token |
| `freshdesk` | Tickets updated since the last run | API key |
| `intercom` | Conversations, in the US, EU or AU data region | access token |
| `gong` | Call transcripts, customer speech only | access key and secret |

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

More complete setups are on the [Examples](/examples/) page.

## Reddit plugin

`reddit` is an unpublished community plugin. Install it from the repository, then allow it in
`obsei.yaml` with `plugins: [reddit]`:

```bash
pip install "obsei-reddit @ git+https://github.com/obsei/obsei#subdirectory=plugins/obsei-reddit"
# or, with uv tool:
uv tool install "obsei[mcp]>=1.0.0a1" \
  --with "obsei-reddit @ git+https://github.com/obsei/obsei#subdirectory=plugins/obsei-reddit"
```

## Global coverage

Use the country and language filters to follow every market you serve: `appstore.countries`
takes ISO 3166 alpha-2 codes (`us`, `br`, `jp`, `in`, `ng`, ...), `appstoreconnect.territories`
takes alpha-3 codes (`USA`, `BRA`, `JPN`, `IND`, `NGA`), and `bluesky.lang` filters by language.
Records keep their original language; enrichers never translate the stored text.
