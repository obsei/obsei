"""Every example config in examples/ must load with the real loader and name real plugins."""

from collections.abc import Callable
from importlib.metadata import entry_points
from pathlib import Path

import httpx
import pytest
from pydantic import BaseModel

from obsei.config import ObseiConfig, PluginSpec, builtin_registry, load_config
from obsei.core.context import Context
from obsei.core.plugin import Factory
from obsei.core.record import Record
from obsei.core.registry import ENTRY_POINT_GROUP

EXAMPLES = Path(__file__).resolve().parents[3] / "examples"
FILES = sorted(EXAMPLES.rglob("*.yaml"))
INSTALLED = {ep.name for ep in entry_points(group=ENTRY_POINT_GROUP)}


def _validated(factory: Factory[object], spec: PluginSpec) -> BaseModel:
    return factory.config_model.model_validate(spec.config)


def _check_llm(config: ObseiConfig, name: str | None, where: str) -> None:
    if name is not None:
        assert name in config.llms, f"{where}: no llms entry named {name!r}"


def test_examples_exist() -> None:
    names = {p.name for p in FILES}
    assert {"social-listening.yaml", "enterprise-air-gapped.yaml"} <= names


@pytest.mark.parametrize("path", FILES, ids=lambda p: str(p.relative_to(EXAMPLES)))
def test_example_is_valid(path: Path) -> None:
    config = load_config(path)
    missing = sorted(set(config.plugins) - INSTALLED)
    if missing:
        pytest.skip(f"needs plugins that are not installed: {', '.join(missing)}")
    registry = builtin_registry(config.plugins)

    for pipeline in config.pipelines:
        keys = [s.key for s in pipeline.sources]
        assert len(keys) == len(set(keys)), f"{pipeline.name}: duplicate source keys"
        for source in pipeline.sources:
            _validated(registry.source(source.type), source)
        for enricher in pipeline.enrichers:
            model = _validated(registry.enricher(enricher.type), enricher)
            where = f"{pipeline.name}/{enricher.type}"
            _check_llm(config, getattr(model, "llm", None), where)
            _check_llm(config, getattr(model, "fallback_llm", None), where)
        for sink in pipeline.sinks:
            _validated(registry.sink(sink.type), sink)
        pipeline.router()
    for alert in config.alerts:
        for target in alert.to:
            _validated(registry.sink(target.type), target)

    themes = config.themes
    _check_llm(config, themes.labeler, "themes.labeler")
    if themes.embedder not in ("auto", "hashing") and not themes.embedder.startswith("local"):
        _check_llm(config, themes.embedder, "themes.embedder")
        assert config.llms[themes.embedder].embedding_model, "themes.embedder needs embedding_model"
    if config.llms:
        _check_llm(config, config.ask_llm, "ask_llm")


def test_unknown_keys_are_rejected(tmp_path: Path) -> None:
    good = (EXAMPLES / "social-listening.yaml").read_text(encoding="utf-8")
    bad = tmp_path / "bad.yaml"
    bad.write_text(good.replace("text_format: html", "text_fromat: html"), encoding="utf-8")
    config = load_config(bad)
    registry = builtin_registry()
    mastodon = next(s for s in config.pipelines[0].sources if s.key == "mastodon")
    with pytest.raises(ValueError, match="text_fromat"):
        _validated(registry.source(mastodon.type), mastodon)


def _recipe(name: str, handler: Callable[[httpx.Request], httpx.Response]) -> list[Record]:
    """The records the example's first source reads from a mocked API."""
    source = load_config(EXAMPLES / name).pipelines[0].sources[0]
    client = httpx.Client(transport=httpx.MockTransport(handler))
    built = builtin_registry().source(source.type).create(source.config, Context(http=client))
    return [record for record, _ in built.fetch(None)]


def test_atlassian_marketplace_recipe() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if "offset" in request.url.params:
            return httpx.Response(200, json={"_embedded": {"reviews": []}})
        review = {
            "id": "r1",
            "review": "Great app, slow support.",
            "stars": 4,
            "date": "2026-09-11T14:18:38.371942301Z",
            "hosting": "cloud",
            "_embedded": {"author": {"name": "Pat"}},
        }
        unwritten = {"id": "r2", "stars": 5, "date": "2026-09-10T00:00:00Z"}
        return httpx.Response(
            200,
            json={
                "_embedded": {"reviews": [review, unwritten]},
                "_links": {"next": {"href": "/rest/2/addons/x/reviews?offset=50&limit=50"}},
            },
        )

    (record,) = _recipe("atlassian-marketplace-reviews.yaml", handler)
    assert (record.text, record.rating, record.source.native_id) == (
        "Great app, slow support.",
        4,
        "r1",
    )
    assert record.context == {"hosting": "cloud"}


def test_google_business_profile_recipe(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GBP_ACCESS_TOKEN", "ya29.token")
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        if "pageToken" in request.url.params:
            return httpx.Response(200, json={"reviews": []})
        review = {
            "reviewId": "g1",
            "reviewer": {"displayName": "Ana"},
            "starRating": "TWO",
            "comment": "Queue was long.",
            "updateTime": "2026-09-01T10:00:00Z",
        }
        return httpx.Response(200, json={"reviews": [review], "nextPageToken": "n2"})

    (record,) = _recipe("google-business-reviews.yaml", handler)
    assert (record.text, record.context) == ("Queue was long.", {"starRating": "TWO"})
    assert seen[0].headers["authorization"] == "Bearer ya29.token"
    assert seen[0].url.params["pageSize"] == "50"
    assert seen[1].url.params["pageToken"] == "n2"


def test_confluence_recipe(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CONFLUENCE_AUTH", "Basic eW91OnRva2Vu")
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        if "cursor" in request.url.params:
            return httpx.Response(200, json={"results": []})
        page = {
            "id": "42",
            "title": "Interview: Acme",
            "createdAt": "2026-08-01T09:00:00.000Z",
            "body": {"storage": {"value": "<p>Exports are <b>too slow</b>.</p><p>Wants SSO.</p>"}},
        }
        link = '</wiki/api/v2/pages?cursor=abc>; rel="next"'
        return httpx.Response(200, json={"results": [page]}, headers={"Link": link})

    (record,) = _recipe("confluence-pages.yaml", handler)
    assert record.text == "Interview: Acme\n\nExports are too slow.\nWants SSO."
    assert seen[0].url.params["space-id"] == "123456"
    assert str(seen[1].url) == "https://acme.atlassian.net/wiki/api/v2/pages?cursor=abc"
    assert all(r.headers["authorization"] == "Basic eW91OnRva2Vu" for r in seen)


def test_wordpress_reviews_recipe() -> None:
    item = (
        "<item><guid>https://wordpress.org/support/topic/good-9217/</guid>"
        "<title>Good! (5 stars)</title><pubDate>Wed, 14 Oct 2026 11:12:22 +0000</pubDate>"
        "<description><![CDATA[<p>Replies: 0</p><p>Rating: 5 stars</p><p>Good!</p>]]>"
        "</description></item>"
    )
    feed = f"<rss version='2.0'><channel>{item}</channel></rss>"
    (record,) = _recipe("wordpress-plugin-reviews.yaml", lambda r: httpx.Response(200, text=feed))
    assert record.text == "Good! (5 stars)\n\nReplies: 0\nRating: 5 stars\nGood!"
