import logging
from datetime import datetime

import requests

from typing import Any, Dict, List, Optional

from pydantic import BaseSettings, Field
from pydantic.types import SecretStr
from searchtweets import collect_results, gen_request_parameters

from obsei.source.base_source import BaseSource, BaseSourceConfig
from obsei.analyzer.text_analyzer import AnalyzerRequest

import preprocessor as cleaning_processor

from obsei.misc.utils import convert_utc_time

logger = logging.getLogger(__name__)

TWITTER_OAUTH_ENDPOINT = 'https://api.twitter.com/oauth2/token'

DEFAULT_MAX_TWEETS = 10

DEFAULT_TWEET_FIELDS = [
    "author_id", "conversation_id", "created_at", "entities", "geo", "id", "in_reply_to_user_id", "lang",
    "public_metrics", "referenced_tweets", "source", "text"
]
DEFAULT_EXPANSIONS = [
    "author_id", "entities.mentions.username", "geo.place_id", "in_reply_to_user_id", "referenced_tweets.id",
    "referenced_tweets.id.author_id"
]
DEFAULT_PLACE_FIELDS = ["contained_within", "country", "country_code", "full_name", "geo", "id", "name", "place_type"]
DEFAULT_USER_FIELDS = [
    "created_at", "description", "entities", "id", "location", "name", "public_metrics", "url", "username", "verified"
]
DEFAULT_OPERATORS = [
    "-is:reply",
    "-is:retweet"
]


class TwitterCredentials(BaseSettings):
    bearer_token: Optional[SecretStr] = Field(None, env='twitter_bearer_token')
    consumer_key: Optional[SecretStr] = Field(None, env='twitter_consumer_key')
    consumer_secret: Optional[SecretStr] = Field(None, env='twitter_consumer_secret')
    endpoint: str = Field("https://api.twitter.com/2/tweets/search/recent", env='twitter_endpoint')
    extra_headers_dict: Optional[Dict[str, Any]] = None

    def __init__(self, **data: Any):
        super().__init__(**data)
        if self.bearer_token is None:
            if self.consumer_key is None and self.consumer_secret is None:
                raise AttributeError("consumer_key and consumer_secret required to generate bearer_token via Twitter")

            self.bearer_token = SecretStr(self.generate_bearer_token())

    def get_twitter_credentials(self):
        if self.bearer_token is None:
            self.bearer_token = self.generate_bearer_token()

        return {
            "bearer_token": self.bearer_token.get_secret_value(),
            "endpoint": self.endpoint,
            "extra_headers_dict": self.extra_headers_dict,
        }

    # Copied from Twitter searchtweets-v2 lib
    def generate_bearer_token(self):
        """
        Return the bearer token for a given pair of consumer key and secret values.
        """
        data = [('grant_type', 'client_credentials')]
        resp = requests.post(
            TWITTER_OAUTH_ENDPOINT,
            data=data,
            auth=(
                self.consumer_key.get_secret_value(),
                self.consumer_secret.get_secret_value()
            )
        )
        logger.warning("Grabbing bearer token from OAUTH")
        if resp.status_code >= 400:
            logger.error(resp.text)
            resp.raise_for_status()

        return resp.json()['access_token']

    class Config:
        arbitrary_types_allowed = True


class TwitterSourceConfig(BaseSourceConfig):
    TYPE: str = "Twitter"
    query: Optional[str] = None
    keywords: Optional[List[str]] = None
    hashtags: Optional[List[str]] = None
    usernames: Optional[List[str]] = None
    operators: Optional[List[str]] = Field(DEFAULT_OPERATORS)
    since_id: Optional[int] = None
    until_id: Optional[int] = None
    lookup_period: str = None
    tweet_fields: Optional[List[str]] = Field(DEFAULT_TWEET_FIELDS)
    user_fields: Optional[List[str]] = Field(DEFAULT_USER_FIELDS)
    expansions: Optional[List[str]] = Field(DEFAULT_EXPANSIONS)
    place_fields: Optional[List[str]] = Field(DEFAULT_PLACE_FIELDS)
    max_tweets: Optional[int] = DEFAULT_MAX_TWEETS
    credential: Optional[TwitterCredentials] = None

    def __init__(self, **data: Any):
        super().__init__(**data)
        if self.credential is None:
            self.credential = TwitterCredentials()


class TwitterSource(BaseSource):
    NAME: str = "Twitter"

    def lookup(
        self,
        config: TwitterSourceConfig,
        **kwargs
    ) -> List[AnalyzerRequest]:
        if not config.query and not config.keywords and not config.hashtags and config.usernames:
            raise AttributeError("At least one non empty parameter required (query, keywords, hashtags, and usernames)")

        place_fields = ",".join(config.place_fields) if config.place_fields is not None else None
        user_fields = ",".join(config.user_fields) if config.user_fields is not None else None
        expansions = ",".join(config.expansions) if config.expansions is not None else None
        tweet_fields = ",".join(config.tweet_fields) if config.tweet_fields is not None else None

        # Get data from state
        id: str = kwargs.get("id", None)
        state: Dict[str, Any] = None if id is None else self.store.get_source_state(id)
        since_id: Optional[int] = config.since_id or None if state is None else state.get("since_id", None)
        until_id: Optional[int] = config.until_id or None if state is None else state.get("until_id", None)
        update_state: bool = True if id else False
        state = state or dict()
        max_tweet_id = since_id
        min_tweet_id = until_id
        lookup_period = config.lookup_period
        start_time = None if lookup_period is None else datetime.strptime(
            convert_utc_time(lookup_period), "%Y-%m-%dT%H:%M:%S%z"
        )

        if since_id or until_id:
            lookup_period = None

        query = self._generate_query_string(
            query=config.query,
            keywords=config.keywords,
            hashtags=config.hashtags,
            usernames=config.usernames,
            operators=config.operators
        )

        source_responses: List[AnalyzerRequest] = []
        need_more_lookup = True
        while need_more_lookup:
            search_query = gen_request_parameters(
                query=query,
                results_per_call=config.max_tweets,
                place_fields=place_fields,
                expansions=expansions,
                user_fields=user_fields,
                tweet_fields=tweet_fields,
                since_id=since_id,
                until_id=until_id,
                start_time=lookup_period
            )
            logger.info(search_query)

            tweets_output = collect_results(
                query=search_query,
                max_tweets=config.max_tweets,
                result_stream_args=config.credential.get_twitter_credentials()
            )

            if not tweets_output:
                logger.info("No Tweets found")
                need_more_lookup = False
                break

            tweets = []
            users = []
            meta_info = None
            for raw_output in tweets_output:
                if "text" in raw_output:
                    tweets.append(raw_output)
                elif "users" in raw_output:
                    users = raw_output["users"]
                elif "meta" in raw_output:
                    meta_info = raw_output["meta"]

            # Extract user info and create user map
            user_map: Dict[str, Dict[str, Any]] = {}
            if len(users) > 0 and "id" in users[0]:
                for user in users:
                    user_map[user["id"]] = user

            # TODO use it later
            logger.info(f"Twitter API meta_info='{meta_info}'")

            for tweet in tweets:
                if "author_id" in tweet and tweet["author_id"] in user_map:
                    tweet["author_info"] = user_map.get(tweet["author_id"])

                source_responses.append(self._get_source_output(tweet))

                # Get latest tweet id
                current_tweet_id = int(tweet["id"])

                logger.info(f'{tweet["created_at"]}:{current_tweet_id}:{since_id}:{until_id}')

                if start_time:
                    created_date = datetime.strptime(tweet["created_at"], "%Y-%m-%dT%H:%M:%S.%f%z")
                    if start_time > created_date:
                        need_more_lookup = False
                        break

                if max_tweet_id is None:
                    max_tweet_id = current_tweet_id
                if min_tweet_id is None:
                    min_tweet_id = current_tweet_id
                if max_tweet_id < current_tweet_id:
                    max_tweet_id = current_tweet_id
                if min_tweet_id > current_tweet_id:
                    min_tweet_id = current_tweet_id

            logger.info(f'{max_tweet_id}:{min_tweet_id}')
            until_id = min_tweet_id
            lookup_period = None

        if update_state:
            state["since_id"] = max_tweet_id
            self.store.update_source_state(workflow_id=id, state=state)

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
            and_query_str = f' ({" ".join(and_tokens)})' if and_tokens else ''

        return or_query_str + and_query_str

    def _get_source_output(self, tweet: Dict[str, Any]):
        tweet_url = TwitterSource.get_tweet_url(tweet["text"])
        processed_text = TwitterSource.clean_tweet_text(tweet["text"])

        tweet["tweet_url"] = tweet_url
        return AnalyzerRequest(
            processed_text=processed_text,
            meta=tweet,
            source_name=self.NAME
        )

    @staticmethod
    def clean_tweet_text(tweet_text: str):
        return cleaning_processor.clean(tweet_text)

    @staticmethod
    def get_tweet_url(tweet_text: str):
        parsed_tweet = cleaning_processor.parse(tweet_text)
        tweet_url = None
        if not parsed_tweet.urls:
            return tweet_url

        last_index = len(tweet_text)
        for url_info in parsed_tweet.urls:
            if url_info.end_index == last_index:
                tweet_url = url_info.match
                break

        return tweet_url
