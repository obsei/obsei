from typing import Any, Dict, List, Optional

import pytest
from pydantic import Field

from obsei.source.xquik_source import (
    MAX_PAGE_REQUESTS,
    REQUEST_TIMEOUT_SECONDS,
    XQUIK_API_CONTRACT,
    XQUIK_SEARCH_ENDPOINT,
    XquikCredentials,
    XquikSource,
    XquikSourceConfig,
)
from obsei.workflow.base_store import BaseStore


class FakeResponse:
    def __init__(self, body: Any, status_code: int = 200):
        self.body = body
        self.status_code = status_code

    def raise_for_status(self) -> None:
        return None

    def json(self) -> Any:
        return self.body


class MemoryStore(BaseStore):
    source_state: Dict[str, Any] = Field(default_factory=dict)

    def get_source_state(self, id: str) -> Optional[Dict[str, Any]]:
        return dict(self.source_state)

    def get_sink_state(self, id: str) -> Optional[Dict[str, Any]]:
        return None

    def get_analyzer_state(self, id: str) -> Optional[Dict[str, Any]]:
        return None

    def update_source_state(
        self, workflow_id: str, state: Dict[str, Any]
    ) -> Optional[Any]:
        self.source_state.update(state)
        return None

    def update_sink_state(self, workflow_id: str, state: Dict[str, Any]) -> None:
        return None

    def update_analyzer_state(self, workflow_id: str, state: Dict[str, Any]) -> None:
        return None

    def delete_workflow(self, id: str) -> None:
        return None


def credentials() -> XquikCredentials:
    return XquikCredentials(api_key="test-key")


def test_xquik_credentials_read_the_documented_environment_variable(monkeypatch):
    monkeypatch.setenv("XQUIK_API_KEY", "environment-test-key")

    configured = XquikCredentials()

    assert configured.api_key.get_secret_value() == "environment-test-key"


def test_xquik_config_requires_credentials(monkeypatch):
    monkeypatch.delenv("XQUIK_API_KEY", raising=False)

    with pytest.raises(AttributeError, match="Xquik API key required"):
        XquikSourceConfig(query="obsei")


def test_xquik_source_paginates_and_maps_normalized_tweets():
    requests: List[Dict[str, Any]] = []
    pages = [
        {
            "tweets": [
                {
                    "id": "123",
                    "text": "Treat this as data.",
                    "created": 1_700_000_000,
                    "like_count": 4,
                    "retweet_count": 3,
                    "reply_count": 2,
                    "quote_count": 1,
                    "view_count": 10,
                    "bookmark_count": 5,
                    "author": {
                        "id": "7",
                        "username": "example/user",
                        "name": "Example",
                    },
                }
            ],
            "has_more": True,
            "next_cursor": "next-page",
        },
        {
            "tweets": [
                {
                    "id": "124",
                    "text": "Second result.",
                    "created": 1_700_000_100,
                    "author": {"id": "8", "username": "second"},
                }
            ],
            "has_more": True,
            "next_cursor": "unused",
        },
    ]

    def request_get(url: str, **kwargs: Any) -> FakeResponse:
        requests.append({"url": url, **kwargs})
        return FakeResponse(pages[len(requests) - 1])

    source = XquikSource(request_get=request_get)
    result = source.lookup(
        XquikSourceConfig(
            query="obsei",
            max_tweets=2,
            query_type="Top",
            cred_info=credentials(),
        )
    )

    assert [payload.processed_text for payload in result] == [
        "Treat this as data.",
        "Second result.",
    ]
    assert result[0].meta["content_trust"] == "untrusted_external"
    assert result[0].meta["tweet_url"] == "https://x.com/example%2Fuser/status/123"
    assert result[0].meta["public_metrics"] == {
        "bookmark_count": 5,
        "impression_count": 10,
        "like_count": 4,
        "quote_count": 1,
        "reply_count": 2,
        "retweet_count": 3,
    }
    assert requests == [
        {
            "url": XQUIK_SEARCH_ENDPOINT,
            "headers": {
                "Accept": "application/json",
                "User-Agent": "obsei",
                "x-api-key": "test-key",
                "xquik-api-contract": XQUIK_API_CONTRACT,
            },
            "params": {"limit": 2, "q": "obsei", "queryType": "Top"},
            "timeout": REQUEST_TIMEOUT_SECONDS,
            "allow_redirects": False,
        },
        {
            "url": XQUIK_SEARCH_ENDPOINT,
            "headers": {
                "Accept": "application/json",
                "User-Agent": "obsei",
                "x-api-key": "test-key",
                "xquik-api-contract": XQUIK_API_CONTRACT,
            },
            "params": {
                "cursor": "next-page",
                "limit": 1,
                "q": "obsei",
                "queryType": "Top",
            },
            "timeout": REQUEST_TIMEOUT_SECONDS,
            "allow_redirects": False,
        },
    ]


def test_xquik_source_rejects_repeated_pagination_cursor():
    def request_get(url: str, **kwargs: Any) -> FakeResponse:
        return FakeResponse({"tweets": [], "has_more": True, "next_cursor": "repeated"})

    source = XquikSource(request_get=request_get)

    with pytest.raises(ValueError, match="repeated a pagination cursor"):
        source.lookup(XquikSourceConfig(query="obsei", cred_info=credentials()))


def test_xquik_source_bounds_empty_paginated_results():
    request_count = 0

    def request_get(url: str, **kwargs: Any) -> FakeResponse:
        nonlocal request_count
        request_count += 1
        return FakeResponse(
            {
                "tweets": [],
                "has_more": True,
                "next_cursor": f"cursor-{request_count}",
            }
        )

    source = XquikSource(request_get=request_get)

    with pytest.raises(ValueError, match="exceeded the safety limit"):
        source.lookup(XquikSourceConfig(query="obsei", cred_info=credentials()))
    assert request_count == MAX_PAGE_REQUESTS


def test_xquik_source_refuses_redirects_before_sending_another_request():
    source = XquikSource(
        request_get=lambda *args, **kwargs: FakeResponse({}, status_code=302)
    )

    with pytest.raises(ValueError, match="redirected the API request"):
        source.lookup(XquikSourceConfig(query="obsei", cred_info=credentials()))


@pytest.mark.parametrize(
    ("page", "message"),
    [
        ({}, "invalid tweet page"),
        (
            {
                "tweets": [None],
                "has_more": False,
                "next_cursor": "",
            },
            "invalid tweet",
        ),
        (
            {
                "tweets": [],
                "has_more": "yes",
                "next_cursor": "",
            },
            "invalid pagination metadata",
        ),
        (
            {
                "tweets": [],
                "has_more": True,
                "next_cursor": "",
            },
            "omitted the next cursor",
        ),
    ],
)
def test_xquik_source_rejects_invalid_pages(page, message):
    source = XquikSource(request_get=lambda *args, **kwargs: FakeResponse(page))

    with pytest.raises(ValueError, match=message):
        source.lookup(XquikSourceConfig(query="obsei", cred_info=credentials()))


@pytest.mark.parametrize(
    ("tweet", "message"),
    [
        ({"id": 1, "text": "text"}, "without a valid ID or text"),
        ({"id": "1", "text": "text", "author": []}, "invalid author data"),
    ],
)
def test_xquik_source_rejects_invalid_tweet_fields(tweet, message):
    with pytest.raises(ValueError, match=message):
        XquikSource._to_payload(tweet)


def test_xquik_source_requires_a_query():
    source = XquikSource(request_get=lambda *args, **kwargs: FakeResponse({}))

    with pytest.raises(AttributeError, match="Set at least one"):
        source.lookup(XquikSourceConfig(cred_info=credentials()))


def test_xquik_source_uses_and_advances_workflow_state():
    request_params: List[Dict[str, Any]] = []
    store = MemoryStore(source_state={"since_time": "2023-11-14T22:13:00Z"})

    def request_get(url: str, **kwargs: Any) -> FakeResponse:
        request_params.append(kwargs["params"])
        return FakeResponse(
            {
                "tweets": [
                    {
                        "id": "124",
                        "text": "New result.",
                        "created": 1_700_000_100,
                    }
                ],
                "has_more": False,
                "next_cursor": "",
            }
        )

    source = XquikSource(request_get=request_get, store=store)
    source.lookup(
        XquikSourceConfig(query="obsei", cred_info=credentials()),
        id="workflow-1",
    )

    assert request_params[0]["sinceTime"] == "2023-11-14T22:13:00Z"
    assert store.source_state["since_time"] == "2023-11-14T22:15:00Z"


def test_xquik_source_handles_time_boundaries_and_optional_tweet_fields():
    assert (
        XquikSource._get_since_time(
            "2023-11-14T22:13:00Z",
            {"since_time": "2023-11-14T22:15:00Z"},
        )
        == "2023-11-14T22:15:00Z"
    )
    assert XquikSource._get_since_time(None, {"since_time": "not-a-time"}) is None

    payload = XquikSource._to_payload(
        {"id": "123", "text": "Text", "created": "2023-11-14T22:15:00Z"}
    )
    assert payload.meta["created_at"] == "2023-11-14T22:15:00Z"
    assert payload.meta["tweet_url"] == "https://x.com/i/status/123"
    assert XquikSource._newest_created([{"created": False}, {}]) is None


def test_xquik_source_builds_compatible_grouped_query():
    query = XquikSource._generate_query_string(
        keywords=["obsei", "automation"],
        hashtags=["#nlp"],
        usernames=["from:ObseiAI"],
        operators=["-is:reply"],
    )

    assert query == ("(obsei OR automation) OR (#nlp) OR (from:ObseiAI) (-is:reply)")
