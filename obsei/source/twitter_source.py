import logging
from datetime import datetime

import pytz
import requests

from typing import Any, Dict, List, Optional

from pydantic import BaseSettings, Field
from pydantic.types import SecretStr
from searchtweets import collect_results, gen_request_parameters

from obsei.source.base_source import BaseSource, BaseSourceConfig
from obsei.payload import TextPayload

import preprocessor as cleaning_processor

from obsei.misc.utils import convert_utc_time

logger = logging.getLogger(__name__)

TWITTER_OAUTH_ENDPOINT = "https://api.twitter.com/oauth2/token"

DEFAULT_MAX_TWEETS = 10

DEFAULT_TWEET_FIELDS = [
    "author_id",
    "conversation_id",
    "created_at",
    "entities",
    "geo",
    "id",
    "in_reply_to_user_id",
    "lang",
    "public_metrics",
    "referenced_tweets",
    "source",
    "text",
    "withheld",
]
DEFAULT_EXPANSIONS = [
    "author_id",
    "entities.mentions.username",
    "geo.place_id",
    "in_reply_to_user_id",
    "referenced_tweets.id",
    "referenced_tweets.id.author_id",
]
DEFAULT_PLACE_FIELDS = [
    "contained_within",
    "country",
    "country_code",
    "full_name",
    "geo",
    "id",
    "name",
    "place_type",
]
DEFAULT_USER_FIELDS = [
    "created_at",
    "description",
    "entities",
    "id",
    "location",
    "name",
    "public_metrics",
    "url",
    "username",
    "verified",
]
DEFAULT_OPERATORS = ["-is:reply", "-is:retweet"]


class TwitterCredentials(BaseSettings):
    bearer_token: Optional[SecretStr] = Field(None, env="twitter_bearer_token")
    consumer_key: Optional[SecretStr] = Field(None, env="twitter_consumer_key")
    consumer_secret: Optional[SecretStr] = Field(None, env="twitter_consumer_secret")
    endpoint: str = Field(
        "https://api.twitter.com/2/tweets/search/recent", env="twitter_endpoint"
    )
    extra_headers_dict: Optional[Dict[str, Any]] = None


class TwitterSourceConfig(BaseSourceConfig):
    TYPE: str = "Twitter"
    query: Optional[str] = None
    keywords: Optional[List[str]] = None
    hashtags: Optional[List[str]] = None
    usernames: Optional[List[str]] = None
    operators: Optional[List[str]] = Field(DEFAULT_OPERATORS)
    since_id: Optional[int] = None
    until_id: Optional[int] = None
    lookup_period: Optional[str] = None
    tweet_fields: Optional[List[str]] = Field(DEFAULT_TWEET_FIELDS)
    user_fields: Optional[List[str]] = Field(DEFAULT_USER_FIELDS)
    expansions: Optional[List[str]] = Field(DEFAULT_EXPANSIONS)
    place_fields: Optional[List[str]] = Field(DEFAULT_PLACE_FIELDS)
    max_tweets: int = DEFAULT_MAX_TWEETS
    cred_info: TwitterCredentials = Field(None)
    credential: Optional[TwitterCredentials] = None

    def __init__(self, **data: Any):
        super().__init__(**data)

        self.cred_info = self.cred_info or TwitterCredentials()

        if self.credential is not None:
            logger.warning("`credential` is deprecated; use `cred_info`")
            self.cred_info = self.credential

        if self.cred_info.bearer_token is None:
            if self.cred_info.consumer_key is None and self.cred_info.consumer_secret is None:
                raise AttributeError(
                    "consumer_key and consumer_secret required to generate bearer_token via Twitter"
                )

            self.cred_info.bearer_token = SecretStr(self.generate_bearer_token())

        if self.max_tweets > 100:
            logger.warning("Twitter API support max 100 tweets per call, hence resetting `max_tweets` to 100")
            self.max_tweets = 100

    def get_twitter_credentials(self):
        if self.cred_info.bearer_token is None:
            self.cred_info.bearer_token = self.generate_bearer_token()

        return {
            "bearer_token": self.cred_info.bearer_token.get_secret_value(),
            "endpoint": self.cred_info.endpoint,
            "extra_headers_dict": self.cred_info.extra_headers_dict,
        }

    # Copied from Twitter searchtweets-v2 lib
    def generate_bearer_token(self):
        """
        Return the bearer token for a given pair of consumer key and secret values.
        """
        data = [("grant_type", "client_credentials")]
        resp = requests.post(
            TWITTER_OAUTH_ENDPOINT,
            data=data,
            auth=(
                self.cred_info.consumer_key.get_secret_value(),
                self.cred_info.consumer_secret.get_secret_value(),
            ),
        )
        logger.warning("Grabbing bearer token from OAUTH")
        if resp.status_code >= 400:
            logger.error(resp.text)
            resp.raise_for_status()

        return resp.json()["access_token"]


class TwitterSource(BaseSource):
    NAME: str = "Twitter"

    def lookup(self, config: TwitterSourceConfig, **kwargs) -> List[TextPayload]:  # type: ignore[override]
        if (
            not config.query
            and not config.keywords
            and not config.hashtags
            and config.usernames
        ):
            raise AttributeError(
                "At least one non empty parameter required (query, keywords, hashtags, and usernames)"
            )

        place_fields = (
            ",".join(config.place_fields) if config.place_fields is not None else None
        )
        user_fields = (
            ",".join(config.user_fields) if config.user_fields is not None else None
        )
        expansions = (
            ",".join(config.expansions) if config.expansions is not None else None
        )
        tweet_fields = (
            ",".join(config.tweet_fields) if config.tweet_fields is not None else None
        )

        # Get data from state
        identifier: str = kwargs.get("id", None)
        state: Optional[Dict[str, Any]] = (
            None
            if identifier is None or self.store is None
            else self.store.get_source_state(identifier)
        )
        since_id: Optional[int] = (
            config.since_id or None if state is None else state.get("since_id", None)
        )
        until_id: Optional[int] = (
            config.until_id or None if state is None else state.get("until_id", None)
        )
        update_state: bool = True if identifier else False
        state = state or dict()
        max_tweet_id = since_id
        min_tweet_id = until_id
        lookup_period = config.lookup_period
        if lookup_period is None:
            start_time = None
        elif len(lookup_period) <= 5:
            start_time = convert_utc_time(lookup_period).replace(tzinfo=pytz.UTC)
        else:
            start_time = datetime.strptime(lookup_period, "%Y-%m-%dT%H:%M:%S%z")

        if since_id or until_id:
            lookup_period = None

        query = self._generate_query_string(
            query=config.query,
            keywords=config.keywords,
            hashtags=config.hashtags,
            usernames=config.usernames,
            operators=config.operators,
        )

        source_responses: List[TextPayload] = []

        search_query = gen_request_parameters(
            granularity=None,
            query=query,
            results_per_call=config.max_tweets,
            place_fields=place_fields,
            expansions=expansions,
            user_fields=user_fields,
            tweet_fields=tweet_fields,
            since_id=since_id,
            until_id=until_id,
            start_time=lookup_period,
            stringify=False,
        )
        logger.info(search_query)

        tweets_output = collect_results(
            query=search_query,
            max_tweets=config.max_tweets,
            result_stream_args=config.get_twitter_credentials(),
        )

        tweets: List[Dict[str, Any]] = []
        users: List[Dict[str, Any]] = []
        meta_info: Dict[str, Any] = {}

        if not tweets_output and len(tweets_output) == 0:
            logger.info("No Tweets found")
        else:
            tweets = tweets_output[0]["data"] if "data" in tweets_output[0] else tweets
            if "includes" in tweets_output[0] and "users" in tweets_output[0]["includes"]:
                users = tweets_output[0]["includes"]["users"]
            meta_info = tweets_output[0]["meta"] if "meta" in tweets_output[0] else meta_info

        # Extract user info and create user map
        user_map: Dict[str, Dict[str, Any]] = {}
        if len(users) > 0 and "id" in users[0]:
            for user in users:
                if "username" in user:
                    user["user_url"] = f'https://twitter.com/{user["username"]}'
                user_map[user["id"]] = user

        logger.info(f"Twitter API meta_info='{meta_info}'")

        for tweet in tweets:
            if "author_id" in tweet and tweet["author_id"] in user_map:
                tweet["author_info"] = user_map.get(tweet["author_id"])

            source_responses.append(self._get_source_output(tweet))

            if start_time:
                created_date = datetime.strptime(
                    tweet["created_at"], "%Y-%m-%dT%H:%M:%S.%f%z"
                )
                if start_time > created_date:
                    break

        max_tweet_id = meta_info["newest_id"] if "newest_id" in meta_info else max_tweet_id
        # min_tweet_id = meta_info["oldest_id"] if "oldest_id" in meta_info else min_tweet_id

        if update_state and self.store is not None:
            state["since_id"] = max_tweet_id
            self.store.update_source_state(workflow_id=identifier, state=state)

        return source_responses

    @staticmethod
    def _generate_query_string(
        query: str = None,
        keywords: List[str] = None,
        hashtags: List[str] = None,
        usernames: List[str] = None,
        operators: List[str] = None,
    ) -> str:
        if query:
            return query

        or_tokens = []
        and_tokens = []

        or_tokens_list = [keywords, hashtags, usernames]
        for tokens in or_tokens_list:
            if tokens:
                if len(tokens) > 0:
                    or_tokens.append(f'({" OR ".join(tokens)})')
                else:
                    or_tokens.append(f'{"".join(tokens)}')

        and_query_str = ""
        or_query_str = ""

        if or_tokens:
            if len(or_tokens) > 0:
                or_query_str = f'{" OR ".join(or_tokens)}'
            else:
                or_query_str = f'{"".join(or_tokens)}'

        if operators:
            and_tokens.append(f'{" ".join(operators)}')

        if and_tokens:
            and_query_str = f' ({" ".join(and_tokens)})' if and_tokens else ""

        return or_query_str + and_query_str

    def _get_source_output(self, tweet: Dict[str, Any]):
        processed_text = TwitterSource.clean_tweet_text(tweet["text"])
        tweet["tweet_url"] = f'https://twitter.com/twitter/statuses/{tweet["id"]}'
        return TextPayload(
            processed_text=processed_text, meta=tweet, source_name=self.NAME
        )

    @staticmethod
    def clean_tweet_text(tweet_text: str):
        return cleaning_processor.clean(tweet_text)
