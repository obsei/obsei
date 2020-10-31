import logging
import os
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from searchtweets import collect_results, gen_request_parameters, load_credentials

from socialtracker.source.twitter_source_config import TwitterSourceConfig
from socialtracker.source.base_source import BaseSource, SourceResponse

logger = logging.getLogger(__name__)

DEFAULT_MAX_TWEETS = 10

DEFAULT_TWEET_FILEDS = [
    "author_id", "entities.mentions.username", "geo.place_id", "in_reply_to_user_id", "referenced_tweets.id",
    "referenced_tweets.id.author_id",
]

DEFAULT_EXPANSIONS = [
    "author_id", "entities.mentions.username", "geo.place_id", "in_reply_to_user_id", "referenced_tweets.id",
    "referenced_tweets.id.author_id"
]

DEFAULT_PLACE_FIELDS = ["country"]

DEFAULT_USER_FIELDS = [
    "public_metrics", "username", "verified", "name"
]

DEFAULT_OPERATORS = [
    "-is:reply",
    "-is:retweet"
]


class TwitterSource(BaseSource):

    def lookup(self, config: TwitterSourceConfig) -> List[SourceResponse]:
        if not config.query and not config.keywords and not config.hashtags and config.usernames:
            raise AttributeError("At least one non empty parameter required (query, keywords, hashtags, and usernames)")

        if config.consumer_key:
            os.environ["SEARCHTWEETS_CONSUMER_KEY"] = config.consumer_key
        if config.consumer_secret:
            os.environ["SEARCHTWEETS_CONSUMER_SECRET"] = config.consumer_secret
        if config.account_type:
            os.environ["SEARCHTWEETS_ACCOUNT_TYPE"] = config.account_type
        if config.bearer_token:
            os.environ["SEARCHTWEETS_BEARER_TOKEN"] = config.bearer_token
        if config.endpoint:
            os.environ["SEARCHTWEETS_ENDPOINT"] = config.endpoint

        search_args = load_credentials(env_overwrite=True)

        place_fields = ",".join(config.place_fields or DEFAULT_PLACE_FIELDS)
        user_fields = ",".join(config.user_fields or DEFAULT_USER_FIELDS)
        expansions = ",".join(config.expansions or DEFAULT_EXPANSIONS)
        tweet_fields = ",".join(config.tweet_fields or DEFAULT_TWEET_FILEDS)

        operators = config.operators or DEFAULT_OPERATORS
        usernames = config.usernames or []
        hashtags = config.hashtags or []
        keywords = config.keywords or []

        max_tweets = config.max_tweets or DEFAULT_MAX_TWEETS

        start_time = None
        if config.lookup_period_in_sec:
            start_time = datetime.utcnow() - timedelta(seconds=config.lookup_period_in_sec)

        query = self._generate_query_string(
            query=config.query,
            keywords=keywords,
            hashtags=hashtags,
            usernames=usernames,
            operators=operators
        )

        search_query = gen_request_parameters(
            query=query,
            results_per_call=max_tweets,
            place_fields=place_fields,
            expansions=expansions,
            user_fields=user_fields,
            tweet_fields=tweet_fields,
            since_id=config.since_id,
            until_id=config.until_id,
            start_time=start_time
        )

        tweets = collect_results(
            query=search_query,
            max_tweets=max_tweets,
            result_stream_args=search_args
        )

        return [TwitterSource.get_source_output(tweet) for tweet in tweets]

    @staticmethod
    def _generate_query_string(
            query: Optional[str] = None,
            keywords=None,
            hashtags=None,
            usernames=None,
            operators=None,
    ) -> str:
        operators = operators or DEFAULT_OPERATORS
        usernames = usernames or []
        hashtags = hashtags or []
        keywords = keywords or []
        or_tokens = []
        and_tokens = []

        if query:
            or_tokens.append(query)

        if keywords:
            or_tokens.append(f'({" OR ".join(keywords)})')

        if hashtags:
            or_tokens.append(f'({" OR ".join(hashtags)})')

        if usernames:
            or_tokens.append(f'({" OR ".join(usernames)})')

        if operators:
            and_tokens.append(f'({" AND ".join(operators)})')

        return f'({" OR ".join(or_tokens)})' + f' AND ({" AND ".join(and_tokens)})' if and_tokens else ''

    @staticmethod
    def get_source_output(tweet: Dict[str, Any]):
        text = tweet["text"]
        return SourceResponse(text, tweet)
