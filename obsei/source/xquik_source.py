import logging
from datetime import datetime, timezone
from typing import Any, Callable, ClassVar, Dict, List, Literal, Optional, Set
from urllib.parse import quote

import requests
from pydantic import Field, PrivateAttr
from pydantic.types import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

from obsei.misc.utils import DATETIME_STRING_PATTERN, convert_utc_time
from obsei.payload import TextPayload
from obsei.source.base_source import BaseSource, BaseSourceConfig

logger = logging.getLogger(__name__)

XQUIK_SEARCH_ENDPOINT = "https://xquik.com/api/v1/x/tweets/search"
XQUIK_API_CONTRACT = "2026-04-29"
DEFAULT_MAX_TWEETS = 20
MAX_TWEETS = 200
REQUEST_TIMEOUT_SECONDS = 15
MAX_PAGE_REQUESTS = 20
DEFAULT_OPERATORS = ["-is:reply", "-is:retweet"]

RequestGet = Callable[..., requests.Response]


class XquikCredentials(BaseSettings):
    model_config = SettingsConfigDict(populate_by_name=True)

    api_key: SecretStr = Field(
        default_factory=lambda: SecretStr(""), alias="XQUIK_API_KEY"
    )


class XquikSourceConfig(BaseSourceConfig):
    TYPE: str = "Xquik"

    query: Optional[str] = None
    keywords: Optional[List[str]] = None
    hashtags: Optional[List[str]] = None
    usernames: Optional[List[str]] = None
    operators: List[str] = Field(default_factory=lambda: DEFAULT_OPERATORS.copy())
    max_tweets: int = Field(DEFAULT_MAX_TWEETS, ge=1, le=MAX_TWEETS)
    lookup_period: Optional[str] = None
    query_type: Literal["Latest", "Top"] = "Latest"
    cred_info: XquikCredentials = Field(default_factory=lambda: XquikCredentials())

    def __init__(self, **data: Any):
        super().__init__(**data)

        if not self.cred_info.api_key.get_secret_value():
            raise AttributeError(
                "Xquik API key required. Set XQUIK_API_KEY or pass "
                "cred_info=XquikCredentials(api_key='...')."
            )


class XquikSource(BaseSource):
    NAME: ClassVar[str] = "Xquik"

    _request_get: RequestGet = PrivateAttr()

    def __init__(self, request_get: Optional[RequestGet] = None, **data: Any) -> None:
        super().__init__(**data)
        self._request_get = request_get or requests.get

    def lookup(  # type: ignore[override]
        self, config: XquikSourceConfig, **kwargs: Any
    ) -> List[TextPayload]:
        query = self._generate_query_string(
            query=config.query,
            keywords=config.keywords,
            hashtags=config.hashtags,
            usernames=config.usernames,
            operators=config.operators,
        )
        if not query:
            raise AttributeError(
                "Set at least one query, keyword, hashtag, or username."
            )

        identifier: Optional[str] = kwargs.get("id")
        state = self._get_state(identifier)
        since_time = self._get_since_time(config.lookup_period, state)

        tweets = self._fetch_tweets(
            api_key=config.cred_info.api_key.get_secret_value(),
            query=query,
            max_tweets=config.max_tweets,
            query_type=config.query_type,
            since_time=since_time,
        )
        source_responses = [self._to_payload(tweet) for tweet in tweets]

        newest_created = self._newest_created(tweets)
        if (
            identifier is not None
            and self.store is not None
            and newest_created is not None
        ):
            state["since_time"] = newest_created
            self.store.update_source_state(workflow_id=identifier, state=state)

        logger.info("Xquik fetched %d tweets", len(source_responses))
        return source_responses

    def _get_state(self, identifier: Optional[str]) -> Dict[str, Any]:
        if identifier is None or self.store is None:
            return {}
        return self.store.get_source_state(identifier) or {}

    @staticmethod
    def _get_since_time(
        lookup_period: Optional[str], state: Dict[str, Any]
    ) -> Optional[str]:
        candidates: List[datetime] = []
        if lookup_period:
            candidates.append(convert_utc_time(lookup_period))

        stored_since_time = state.get("since_time")
        if isinstance(stored_since_time, str):
            try:
                candidates.append(
                    datetime.strptime(
                        stored_since_time, DATETIME_STRING_PATTERN
                    ).replace(tzinfo=timezone.utc)
                )
            except ValueError:
                logger.warning("Ignoring invalid Xquik source state timestamp")

        if not candidates:
            return None
        return max(candidates).strftime(DATETIME_STRING_PATTERN)

    def _fetch_tweets(
        self,
        api_key: str,
        query: str,
        max_tweets: int,
        query_type: str,
        since_time: Optional[str],
    ) -> List[Dict[str, Any]]:
        headers = {
            "Accept": "application/json",
            "User-Agent": "obsei",
            "x-api-key": api_key,
            "xquik-api-contract": XQUIK_API_CONTRACT,
        }
        tweets: List[Dict[str, Any]] = []
        cursor: Optional[str] = None
        seen_cursors: Set[str] = set()
        page_requests = 0

        while len(tweets) < max_tweets:
            page_requests += 1
            if page_requests > MAX_PAGE_REQUESTS:
                raise ValueError("Xquik pagination exceeded the safety limit.")

            params: Dict[str, Any] = {
                "limit": max_tweets - len(tweets),
                "q": query,
                "queryType": query_type,
            }
            if cursor:
                params["cursor"] = cursor
            if since_time:
                params["sinceTime"] = since_time

            response = self._request_get(
                XQUIK_SEARCH_ENDPOINT,
                headers=headers,
                params=params,
                timeout=REQUEST_TIMEOUT_SECONDS,
                allow_redirects=False,
            )
            if 300 <= response.status_code < 400:
                raise ValueError("Xquik redirected the API request.")
            response.raise_for_status()
            page = response.json()
            if not isinstance(page, dict) or not isinstance(page.get("tweets"), list):
                raise ValueError("Xquik returned an invalid tweet page.")

            for tweet in page["tweets"]:
                if not isinstance(tweet, dict):
                    raise ValueError("Xquik returned an invalid tweet.")
                tweets.append(tweet)
                if len(tweets) == max_tweets:
                    break

            has_more = page.get("has_more")
            if not isinstance(has_more, bool):
                raise ValueError("Xquik returned invalid pagination metadata.")
            if not has_more or len(tweets) == max_tweets:
                break

            next_cursor = page.get("next_cursor")
            if not isinstance(next_cursor, str) or not next_cursor:
                raise ValueError("Xquik omitted the next cursor.")
            if next_cursor in seen_cursors:
                raise ValueError("Xquik repeated a pagination cursor.")
            seen_cursors.add(next_cursor)
            cursor = next_cursor

        return tweets

    @staticmethod
    def _to_payload(tweet: Dict[str, Any]) -> TextPayload:
        tweet_id = tweet.get("id")
        text = tweet.get("text")
        author = tweet.get("author", {})
        if not isinstance(tweet_id, str) or not isinstance(text, str):
            raise ValueError("Xquik returned a tweet without a valid ID or text.")
        if not isinstance(author, dict):
            raise ValueError("Xquik returned invalid author data.")

        username = author.get("username")
        safe_username = quote(username, safe="") if isinstance(username, str) else ""
        safe_tweet_id = quote(tweet_id, safe="")
        tweet_url = (
            f"https://x.com/{safe_username}/status/{safe_tweet_id}"
            if safe_username
            else f"https://x.com/i/status/{safe_tweet_id}"
        )

        author_info = dict(author)
        if safe_username:
            author_info["user_url"] = f"https://x.com/{safe_username}"

        meta = dict(tweet)
        meta.update(
            {
                "author_id": author.get("id", ""),
                "author_info": author_info,
                "content_trust": "untrusted_external",
                "created_at": XquikSource._created_at(tweet),
                "public_metrics": {
                    "bookmark_count": tweet.get("bookmark_count", 0),
                    "impression_count": tweet.get("view_count", 0),
                    "like_count": tweet.get("like_count", 0),
                    "quote_count": tweet.get("quote_count", 0),
                    "reply_count": tweet.get("reply_count", 0),
                    "retweet_count": tweet.get("retweet_count", 0),
                },
                "tweet_url": tweet_url,
            }
        )
        return TextPayload(
            processed_text=text,
            segmented_data={},
            meta=meta,
            source_name=XquikSource.NAME,
        )

    @staticmethod
    def _created_at(tweet: Dict[str, Any]) -> str:
        created = tweet.get("created")
        if isinstance(created, (int, float)) and not isinstance(created, bool):
            return datetime.fromtimestamp(created, timezone.utc).strftime(
                DATETIME_STRING_PATTERN
            )
        return created if isinstance(created, str) else ""

    @staticmethod
    def _newest_created(tweets: List[Dict[str, Any]]) -> Optional[str]:
        created_values: List[float] = []
        for tweet in tweets:
            created = tweet.get("created")
            if isinstance(created, (int, float)) and not isinstance(created, bool):
                created_values.append(float(created))
        if not created_values:
            return None
        newest = max(created_values)
        return datetime.fromtimestamp(newest, timezone.utc).strftime(
            DATETIME_STRING_PATTERN
        )

    @staticmethod
    def _generate_query_string(
        query: Optional[str] = None,
        keywords: Optional[List[str]] = None,
        hashtags: Optional[List[str]] = None,
        usernames: Optional[List[str]] = None,
        operators: Optional[List[str]] = None,
    ) -> str:
        if query:
            return query

        groups = []
        for tokens in [keywords, hashtags, usernames]:
            if tokens:
                groups.append(f'({" OR ".join(tokens)})')

        base_query = " OR ".join(groups)
        operator_query = f' ({" ".join(operators)})' if operators else ""
        return base_query + operator_query if base_query else ""
