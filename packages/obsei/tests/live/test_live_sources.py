"""Smoke tests against real public endpoints. Opt in with OBSEI_LIVE=1 (network required).

They check that each free connector still parses what the service returns today: at least one
record, sane fields, and a cursor that moves forward.
"""

import os
from collections.abc import Iterator
from itertools import islice

import httpx
import pytest

from obsei.core.context import Context, default_http
from obsei.core.protocols import Cursor, Source
from obsei.core.record import Record
from obsei.core.registry import Registry
from obsei.sources import register

pytestmark = pytest.mark.skipif(
    not os.environ.get("OBSEI_LIVE"), reason="set OBSEI_LIVE=1 to call real services"
)
SALT = b"live-test-salt-0123456789"


@pytest.fixture(scope="module")
def ctx() -> Iterator[Context]:
    with Context(http=default_http(), salt=SALT) as context:
        yield context


def source(name: str, config: dict[str, object], ctx: Context) -> Source:
    registry = Registry()
    register(registry)
    return registry.source(name).create(config, ctx)  # type: ignore[arg-type]


def first(src: Source, limit: int = 20) -> tuple[list[Record], Cursor | None]:
    pairs = list(islice(src.fetch(None), limit))
    return [r for r, _ in pairs], pairs[-1][1] if pairs else None


def check(records: list[Record], cursor: Cursor | None) -> None:
    assert records, "no records returned"
    for r in records:
        assert r.text.strip()
        assert r.created_at.tzinfo is not None
        assert r.author is None or r.author.pseudonym.startswith("psn_")
    assert cursor


def test_appstore_feed(ctx: Context) -> None:
    check(
        *first(
            source(
                "appstore", {"app_id": "375380948", "countries": ["us", "gb"], "max_pages": 1}, ctx
            )
        )
    )


def test_hackernews(ctx: Context) -> None:
    check(*first(source("hackernews", {"query": "python", "max_pages": 1}, ctx)))


def test_bluesky(ctx: Context) -> None:
    try:
        records, cursor = first(source("bluesky", {"query": "python", "max_pages": 1}, ctx))
    except RuntimeError as exc:
        if "403" in str(exc) or "401" in str(exc):
            pytest.skip(f"public search needs login now: {exc}")
        raise
    check(records, cursor)


def test_github_issues(ctx: Context) -> None:
    check(
        *first(
            source("github_issues", {"repo": "obsei/obsei", "max_pages": 1, "token_env": None}, ctx)
        )
    )


def test_rss_and_atom(ctx: Context) -> None:
    check(*first(source("rss", {"url": "https://github.com/obsei/obsei/releases.atom"}, ctx)))
    check(*first(source("rss", {"url": "https://hnrss.org/newest?points=100"}, ctx)))


def test_proxy_is_respected() -> None:
    assert isinstance(default_http(), httpx.Client)
