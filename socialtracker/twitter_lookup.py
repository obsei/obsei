import os
from typing import Optional

from searchtweets import collect_results, gen_request_parameters, load_credentials

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


class TwitterLookup:
    def __init__(
            self,
            consumer_key: str,
            consumer_secret: str,
            account_type: Optional[str] = None,
            bearer_token: Optional[str] = None,
            endpoint: Optional[str] = None,
    ):
        if consumer_key:
            os.environ["SEARCHTWEETS_CONSUMER_KEY"] = consumer_key
        if consumer_secret:
            os.environ["SEARCHTWEETS_CONSUMER_SECRET"] = consumer_secret
        if account_type:
            os.environ["SEARCHTWEETS_ACCOUNT_TYPE"] = account_type
        if bearer_token:
            os.environ["SEARCHTWEETS_BEARER_TOKEN"] = bearer_token
        if endpoint:
            os.environ["SEARCHTWEETS_ENDPOINT"] = endpoint

        self.search_args = load_credentials(env_overwrite=True)

    def fetch_tweets(
            self,
            query: Optional[str] = None,
            keywords=None,
            hashtags=None,
            usernames=None,
            since_id: Optional[int] = None,
            operators=None,
            tweet_fields=None,
            user_fields=None,
            expansions=None,
            place_fields=None,
            max_tweets=DEFAULT_MAX_TWEETS,
    ):
        if not query and not keywords and not hashtags and usernames:
            raise AttributeError("At least one non empty parameter required (query, keywords, hashtags, and usernames)")

        if place_fields is None:
            place_fields = DEFAULT_PLACE_FIELDS
        if expansions is None:
            expansions = DEFAULT_EXPANSIONS
        if user_fields is None:
            user_fields = DEFAULT_USER_FIELDS
        if tweet_fields is None:
            tweet_fields = DEFAULT_TWEET_FILEDS
        if operators is None:
            operators = DEFAULT_OPERATORS
        if usernames is None:
            usernames = []
        if hashtags is None:
            hashtags = []
        if keywords is None:
            keywords = []

        query = self._generate_query_string(
            query=query,
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
            since_id=since_id
        )

        tweets = collect_results(
            search_query,
            max_tweets=max_tweets,
            result_stream_args=self.search_args
        )

        return tweets

    @staticmethod
    def _generate_query_string(
            query: Optional[str] = None,
            keywords=None,
            hashtags=None,
            usernames=None,
            operators=None,
    ) -> str:
        if operators is None:
            operators = DEFAULT_OPERATORS
        if usernames is None:
            usernames = []
        if hashtags is None:
            hashtags = []
        if keywords is None:
            keywords = []
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
