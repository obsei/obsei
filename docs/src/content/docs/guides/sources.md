---
title: Sources
description: Built-in sources and their configuration.
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
| `reddit` (plugin) | Subreddit posts, comments and searches via RSS | none |
| `sql` | Any SQLAlchemy database or warehouse, incremental by a cursor column | URL in env, `obsei[sql]` |
| `filedrop` | New or changed CSV, JSON Lines and JSON files in a folder (SFTP drop, mounted bucket) | none |
| `imap` | Feedback mailboxes | username and password in env |
| `mcp` | A tool on any MCP server (stdio command or HTTP URL) | `obsei[mcp]` |
| `zendesk` | Tickets, incremental export | email and API token |
| `freshdesk` | Tickets updated since the last run | API key |
| `intercom` | Conversations, in the US, EU or AU data region | access token |
| `gong` | Call transcripts, customer speech only | access key and secret |

## Field mapping

`csv`, `jsonl`, `rest` and `webhook` map fields with dotted paths:

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

## Global coverage

Use the country and language filters to follow every market you serve: `appstore.countries`
takes ISO 3166 alpha-2 codes (`us`, `br`, `jp`, `in`, `ng`, ...), `appstoreconnect.territories`
takes alpha-3 codes (`USA`, `BRA`, `JPN`, `IND`, `NGA`), and `bluesky.lang` filters by language.
Records keep their original language; enrichers never translate the stored text.
