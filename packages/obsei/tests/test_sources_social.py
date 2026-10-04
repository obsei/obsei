import json
from collections.abc import Callable

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec

from obsei.core.context import Context
from obsei.core.protocols import Source
from obsei.core.record import Record
from obsei.core.registry import Registry
from obsei.sources import register

Handler = Callable[[httpx.Request], httpx.Response]


def build(name: str, config: dict[str, object], handler: Handler) -> Source:
    registry = Registry()
    register(registry)
    context = Context(
        http=httpx.Client(transport=httpx.MockTransport(handler)), salt=b"0123456789abcdef-t"
    )
    return registry.source(name).create(json.loads(json.dumps(config)), context)


def records(source: Source) -> list[Record]:
    return [r for r, _ in source.fetch(None)]


def test_hackernews_stories_and_comments() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["numericFilters"] == "created_at_i>0"
        hits = [
            {
                "objectID": "2",
                "comment_text": "<p>Switched to obsei &amp; never looked back</p>",
                "story_id": 1,
                "author": "pg",
                "created_at_i": 1788000100,
            },
            {"objectID": "1", "title": "Show HN: obsei", "author": "x", "created_at_i": 1788000000},
        ]
        return httpx.Response(200, json={"hits": hits, "nbPages": 1})

    result = records(build("hackernews", {"query": "obsei"}, handler))
    assert [r.text for r in result] == ["Show HN: obsei", "Switched to obsei & never looked back"]
    assert result[1].context == {"kind": "comment", "story_id": "1"}


def test_bluesky_hides_urls_by_default() -> None:
    post = {
        "uri": "at://did:plc:abc/app.bsky.feed.post/3k",
        "author": {"did": "did:plc:abc", "handle": "ana.bsky.social"},
        "record": {"text": "obsei es genial", "createdAt": "2026-09-01T00:00:00Z", "langs": ["es"]},
    }

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["lang"] == "es"
        return httpx.Response(200, json={"posts": [post]})

    (hidden,) = records(build("bluesky", {"query": "obsei", "lang": "es"}, handler))
    assert hidden.source.url is None
    assert hidden.lang == "es"
    assert hidden.author is not None
    (shown,) = records(
        build("bluesky", {"query": "obsei", "lang": "es", "include_urls": True}, handler)
    )
    assert shown.source.url == "https://bsky.app/profile/did:plc:abc/post/3k"


def test_youtube_channel_comments(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("YOUTUBE_API_KEY", "k")

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["allThreadsRelatedToChannelId"] == "UC1"
        comment = {
            "id": "c1",
            "snippet": {
                "textOriginal": "Tutorial muito bom",
                "publishedAt": "2026-09-01T00:00:00Z",
                "videoId": "v1",
                "likeCount": 3,
                "authorChannelId": {"value": "UCfan"},
            },
        }
        return httpx.Response(200, json={"items": [{"snippet": {"topLevelComment": comment}}]})

    (comment,) = records(build("youtube", {"channel_id": "UC1"}, handler))
    assert comment.context == {"video_id": "v1", "likes": "3"}
    assert comment.source.url == "https://www.youtube.com/watch?v=v1&lc=c1"


def test_youtube_needs_a_target() -> None:
    with pytest.raises(ValueError, match="video_ids or channel_id"):
        build("youtube", {}, lambda _: httpx.Response(200))


def test_appstoreconnect_signs_es256(monkeypatch: pytest.MonkeyPatch) -> None:
    key = ec.generate_private_key(ec.SECP256R1())
    pem = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode()
    monkeypatch.setenv("ASC_KEY", pem)
    monkeypatch.setenv("ASC_ISSUER_ID", "issuer")
    monkeypatch.setenv("ASC_KEY_ID", "KEY123")

    def handler(request: httpx.Request) -> httpx.Response:
        token = request.headers["Authorization"].removeprefix("Bearer ")
        claims = jwt.decode(
            token, key.public_key(), algorithms=["ES256"], audience="appstoreconnect-v1"
        )
        assert claims["iss"] == "issuer"
        assert jwt.get_unverified_header(token)["kid"] == "KEY123"
        assert request.url.params["filter[territory]"] == "DEU,JPN"
        review = {
            "id": "r1",
            "attributes": {
                "rating": 2,
                "title": "Zu langsam",
                "body": "Seit dem Update sehr langsam.",
                "reviewerNickname": "max",
                "createdDate": "2026-09-01T10:00:00-07:00",
                "territory": "DEU",
            },
        }
        return httpx.Response(200, json={"data": [review], "links": {}})

    config: dict[str, object] = {
        "app_id": "123",
        "private_key_env": "ASC_KEY",
        "territories": ["DEU", "JPN"],
    }
    (review,) = records(build("appstoreconnect", config, handler))
    assert review.text == "Zu langsam\n\nSeit dem Update sehr langsam."
    assert review.context == {"territory": "DEU", "title": "Zu langsam"}
    assert review.rating == 2.0
