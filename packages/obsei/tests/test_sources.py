import json
from collections.abc import Callable, Iterator
from pathlib import Path

import httpx
import pytest

from obsei.core.context import Context
from obsei.core.protocols import Cursor, Source
from obsei.core.record import Record
from obsei.core.registry import Registry
from obsei.sources import register
from obsei.sources._common import html_to_text, parse_time

SALT = b"0123456789abcdef-test"
Handler = Callable[[httpx.Request], httpx.Response]


def ctx(handler: Handler | None = None) -> Context:
    transport = httpx.MockTransport(handler or (lambda _: httpx.Response(404)))
    return Context(http=httpx.Client(transport=transport), salt=SALT)


def build(name: str, config: dict[str, object], context: Context) -> Source:
    registry = Registry()
    register(registry)
    return registry.source(name).create(json.loads(json.dumps(config)), context)


def drain(items: Iterator[tuple[Record, Cursor]]) -> tuple[list[Record], Cursor | None]:
    pairs = list(items)
    return [record for record, _ in pairs], pairs[-1][1] if pairs else None


def test_registers_all_builtins() -> None:
    registry = Registry()
    register(registry)
    assert registry.names()["source"] == [
        "appstore",
        "appstoreconnect",
        "bluesky",
        "csv",
        "filedrop",
        "freshdesk",
        "github_issues",
        "gong",
        "hackernews",
        "imap",
        "intercom",
        "jsonl",
        "mcp",
        "playstore",
        "rest",
        "rss",
        "sql",
        "webhook",
        "youtube",
        "zendesk",
    ]


def test_parse_time_formats() -> None:
    assert parse_time("2026-09-01T10:00:00Z") == parse_time("Tue, 01 Sep 2026 10:00:00 +0000")
    assert parse_time(0) is not None
    assert parse_time("not a date") is None
    assert html_to_text("<p>Hello&nbsp;<b>world</b></p><p>2</p>") == "Hello world\n2"


def test_csv_maps_fields_and_pseudonymises(tmp_path: Path) -> None:
    path = tmp_path / "survey.csv"
    path.write_text(
        "id,comment,when,score,email,lang,plan\n"
        "1,Muy lento,2026-09-01,2,ana@example.com,es,pro\n"
        "2,,2026-09-01,5,bob@example.com,en,free\n"
        ",素晴らしい,2026-09-02,5,,ja,free\n",
        encoding="utf-8",
    )
    fields = {
        "text": "comment",
        "created_at": "when",
        "rating": "score",
        "author": "email",
        "lang": "lang",
        "context": ["plan"],
    }
    source = build("csv", {"path": str(path), "fields": fields}, ctx())
    records, _ = drain(source.fetch(None))
    assert [r.text for r in records] == ["Muy lento", "素晴らしい"]
    first = records[0]
    assert first.rating == 2.0
    assert first.lang == "es"
    assert first.context == {"plan": "pro"}
    assert first.author is not None
    assert "ana" not in first.author.pseudonym
    assert records[1].source.native_id.startswith("sha_")
    assert records[1].author is None


def test_jsonl_nested_paths(tmp_path: Path) -> None:
    path = tmp_path / "tickets.jsonl"
    rows = [{"ticket": {"id": 7, "body": "Refund please"}, "ts": 1756720000}]
    path.write_text("\n".join(json.dumps(r) for r in rows) + "\n\n", encoding="utf-8")
    fields = {"text": "ticket.body", "id": "ticket.id", "created_at": "ts"}
    records, _ = drain(build("jsonl", {"path": str(path), "fields": fields}, ctx()).fetch(None))
    assert records[0].source.native_id == "7"
    assert records[0].created_at.year == 2025


def test_rest_cursor_pagination_and_since() -> None:
    seen: list[httpx.QueryParams] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.url.params)
        assert request.headers["Authorization"] == "Bearer s3cret"
        if request.url.params.get("cursor") == "p2":
            return httpx.Response(200, json={"data": [{"id": 2, "text": "b", "at": "2026-09-02"}]})
        body = {"data": [{"id": 1, "text": "a", "at": "2026-09-01"}], "meta": {"next": "p2"}}
        return httpx.Response(200, json=body)

    with pytest.MonkeyPatch.context() as mp:
        mp.setenv("API_TOKEN", "s3cret")
        source = build(
            "rest",
            {
                "url": "https://feedback.example.com/api/items",
                "bearer_token_env": "API_TOKEN",
                "items_path": "data",
                "pagination": "cursor",
                "next_path": "meta.next",
                "since_param": "updated_since",
                "fields": {"created_at": "at"},
            },
            ctx(handler),
        )
        records, cursor = drain(source.fetch({"since": "2026-08-01T00:00:00+00:00"}))
    assert [r.text for r in records] == ["a", "b"]
    assert seen[0]["updated_since"] == "2026-08-01T00:00:00+00:00"
    assert cursor == {"since": "2026-09-02T00:00:00+00:00"}


def _apple_entry(review_id: str, updated: str, text: str) -> dict[str, object]:
    return {
        "id": {"label": review_id},
        "author": {"name": {"label": "Tanaka"}},
        "im:rating": {"label": "4"},
        "im:version": {"label": "3.2"},
        "title": {"label": "良い"},
        "content": {"label": text},
        "updated": {"label": updated},
    }


def test_appstore_multi_country_incremental() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        country = request.url.path.split("/")[1]
        if "page=1" not in request.url.path:
            return httpx.Response(200, json={"feed": {}})
        entries = [
            _apple_entry(f"{country}2", "2026-09-02T10:00:00-07:00", "new"),
            _apple_entry(f"{country}1", "2026-09-01T10:00:00-07:00", "old"),
        ]
        return httpx.Response(200, json={"feed": {"entry": entries}})

    source = build("appstore", {"app_id": "123", "countries": ["jp", "br"]}, ctx(handler))
    records, cursor = drain(source.fetch({"br": "2026-09-01T17:00:00+00:00"}))
    assert [r.source.native_id for r in records] == ["jp1", "jp2", "br2"]
    assert records[0].text == "良い\n\nold"
    assert records[0].context == {"country": "jp", "app_version": "3.2", "title": "良い"}
    assert cursor == {"jp": "2026-09-02T17:00:00+00:00", "br": "2026-09-02T17:00:00+00:00"}


def test_playstore_reviews(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PLAY_TOKEN", "t")

    def handler(request: httpx.Request) -> httpx.Response:
        review = {
            "reviewId": "r1",
            "authorName": "Priya",
            "comments": [
                {
                    "userComment": {
                        "text": "ऐप धीमा है",
                        "lastModified": {"seconds": "1788000000"},
                        "starRating": 2,
                        "reviewerLanguage": "hi",
                        "appVersionName": "5.0",
                    }
                },
                {"developerComment": {"text": "Thanks, fixing"}},
            ],
        }
        return httpx.Response(200, json={"reviews": [review]})

    source = build(
        "playstore",
        {"package_name": "com.example.app", "access_token_env": "PLAY_TOKEN"},
        ctx(handler),
    )
    records, cursor = drain(source.fetch(None))
    assert records[0].lang == "hi"
    assert records[0].context == {"app_version": "5.0", "developer_reply": "Thanks, fixing"}
    assert cursor is not None
    assert "since" in cursor


def test_playstore_requires_one_auth() -> None:
    with pytest.raises(ValueError, match="exactly one"):
        build("playstore", {"package_name": "com.example.app"}, ctx())


def test_github_issues_skip_prs_and_follow_links() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.params.get("page") == "2":
            issue = {
                "number": 2,
                "title": "Crash",
                "body": "on start",
                "state": "open",
                "created_at": "2026-09-02T00:00:00Z",
                "updated_at": "2026-09-03T00:00:00Z",
                "user": {"login": "octo"},
                "labels": [{"name": "bug"}],
            }
            return httpx.Response(200, json=[issue])
        pr = {"number": 1, "pull_request": {}, "updated_at": "2026-09-01T00:00:00Z"}
        link = '<https://api.github.com/repos/o/r/issues?page=2>; rel="next"'
        return httpx.Response(200, json=[pr], headers={"Link": link})

    records, cursor = drain(build("github_issues", {"repo": "o/r"}, ctx(handler)).fetch(None))
    assert [r.text for r in records] == ["Crash\n\non start"]
    assert records[0].context == {"kind": "issue", "state": "open", "labels": "bug"}
    assert cursor == {"since": "2026-09-03T00:00:00Z"}


RSS = b"""<?xml version="1.0"?>
<rss version="2.0" xmlns:dc="http://purl.org/dc/elements/1.1/"><channel>
<item><guid>a</guid><title>Bonjour</title>
<description>&lt;p&gt;Tr\xc3\xa8s bien&lt;/p&gt;</description>
<pubDate>Tue, 01 Sep 2026 10:00:00 +0000</pubDate><dc:creator>marie</dc:creator></item>
<item><guid>b</guid><title>Old</title><pubDate>Mon, 31 Aug 2026 10:00:00 +0000</pubDate></item>
</channel></rss>"""

ATOM = b"""<?xml version="1.0"?>
<feed xmlns="http://www.w3.org/2005/Atom"><entry><id>x</id><title>Hallo</title>
<link rel="alternate" href="https://example.com/x"/><updated>2026-09-01T00:00:00Z</updated>
<content type="html">Gut</content><author><name>jan</name></author></entry></feed>"""


def test_rss_and_atom() -> None:
    rss = build(
        "rss", {"url": "https://example.com/rss"}, ctx(lambda _: httpx.Response(200, content=RSS))
    )
    records, cursor = drain(rss.fetch({"since": "2026-08-31T10:00:00+00:00"}))
    assert [r.text for r in records] == ["Bonjour\n\nTrès bien"]
    assert records[0].author is not None
    assert cursor == {"since": "2026-09-01T10:00:00+00:00"}
    atom = build(
        "rss", {"url": "https://example.com/atom"}, ctx(lambda _: httpx.Response(200, content=ATOM))
    )
    (entry,), _ = drain(atom.fetch(None))
    assert entry.text == "Hallo\n\nGut"
    assert entry.source.url == "https://example.com/x"


def test_rss_rejects_entity_expansion() -> None:
    bomb = b'<?xml version="1.0"?><!DOCTYPE x [<!ENTITY a "aaaa">]><rss><channel/></rss>'
    source = build(
        "rss", {"url": "https://example.com/rss"}, ctx(lambda _: httpx.Response(200, content=bomb))
    )
    with pytest.raises(Exception, match="Entit"):
        drain(source.fetch(None))


def test_rest_text_format_html_converts_mastodon_statuses() -> None:
    base = "https://mastodon.example/api/v1/timelines/tag/acme"

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.params.get("max_id") == "1":
            status = {"id": "0", "content": "<p></p>", "created_at": "2026-09-01T09:00:00Z"}
            return httpx.Response(200, json=[status])
        status = {
            "id": "2",
            "content": "<p>App crashes on login&nbsp;<a href='#'>#acme</a></p><p>Please fix</p>",
            "created_at": "2026-09-02T10:00:00Z",
            "url": "https://mastodon.example/@ana/2",
        }
        return httpx.Response(
            200, json=[status], headers={"Link": f'<{base}?max_id=1>; rel="next"'}
        )

    fields = {"text": "content", "url": "url"}
    html = build(
        "rest",
        {"url": base, "pagination": "link", "text_format": "html", "fields": fields},
        ctx(handler),
    )
    records, _ = drain(html.fetch(None))
    assert [r.text for r in records] == ["App crashes on login #acme\nPlease fix"]
    assert records[0].source.url == "https://mastodon.example/@ana/2"

    plain = build("rest", {"url": base, "pagination": "link", "fields": fields}, ctx(handler))
    raw, _ = drain(plain.fetch(None))
    assert [r.text for r in raw] == [
        "<p>App crashes on login&nbsp;<a href='#'>#acme</a></p><p>Please fix</p>",
        "<p></p>",
    ]


def test_rest_pagination_sends_credentials_only_to_the_configured_origin() -> None:
    seen: list[httpx.Request] = []
    pages = {
        "feedback.example.com": ("https://feedback.example.com:443/api/items?page=2", "a"),
        "evil.example.net": (None, "c"),
    }

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        if request.url.params.get("page") == "2":
            return httpx.Response(
                200, json={"data": [{"text": "b"}], "next": "https://evil.example.net/steal"}
            )
        nxt, text = pages[request.url.host]
        return httpx.Response(200, json={"data": [{"text": text}], "next": nxt})

    with pytest.MonkeyPatch.context() as mp:
        mp.setenv("API_TOKEN", "s3cret")
        mp.setenv("API_KEY", "k3y")
        source = build(
            "rest",
            {
                "url": "https://feedback.example.com/api/items",
                "bearer_token_env": "API_TOKEN",
                "secret_headers": {"X-Api-Key": "API_KEY"},
                "headers": {"Accept": "application/json"},
                "items_path": "data",
                "pagination": "next_url",
            },
            ctx(handler),
        )
        records, _ = drain(source.fetch(None))
    assert [r.text for r in records] == ["a", "b", "c"]
    for request in seen[:2]:
        assert request.headers["Authorization"] == "Bearer s3cret"
        assert request.headers["X-Api-Key"] == "k3y"
    leaked = seen[2]
    assert leaked.url.host == "evil.example.net"
    assert "Authorization" not in leaked.headers
    assert "X-Api-Key" not in leaked.headers
    assert leaked.headers["Accept"] == "application/json"
