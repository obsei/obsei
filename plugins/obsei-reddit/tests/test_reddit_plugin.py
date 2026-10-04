import httpx
import pytest

from obsei.core.context import Context
from obsei.core.registry import Registry
from obsei_reddit import RedditConfig, register

FEED = b"""<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom">
<entry><id>t3_abc</id><title>App keeps crashing</title><updated>2026-09-01T00:00:00Z</updated>
<link href="https://www.reddit.com/r/androidapps/comments/abc/"/>
<content type="html">&lt;p&gt;Since 5.0&lt;/p&gt;</content><author><name>/u/someone</name></author>
</entry></feed>"""


def test_feed_urls() -> None:
    assert RedditConfig(subreddit="androidapps").feed_url().endswith("/r/androidapps/new/.rss")
    search = RedditConfig(subreddit="androidapps", kind="search", query="crash login")
    assert "search.rss?q=crash+login&restrict_sr=1&sort=new" in search.feed_url()
    with pytest.raises(ValueError, match="query"):
        RedditConfig(subreddit="androidapps", kind="search")


def test_reddit_source_reuses_rss() -> None:
    registry = Registry()
    register(registry)
    ctx = Context(
        http=httpx.Client(
            transport=httpx.MockTransport(lambda _: httpx.Response(200, content=FEED))
        )
    )
    source = registry.source("reddit").create({"subreddit": "androidapps"}, ctx)
    ((record, _),) = list(source.fetch(None))
    assert record.source.type == "reddit"
    assert record.text == "App keeps crashing\n\nSince 5.0"
    assert record.id.startswith("rec_")
    assert record.author is None
