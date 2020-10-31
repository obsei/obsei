from typing import List, Optional

from socialtracker.source.base_source_config import BaseSourceConfig

DEFAULT_MAX_TWEETS = 10

DEFAULT_TWEET_FIELDS = [
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


class TwitterSourceConfig(BaseSourceConfig):
    def __init__(
        self,
        twitter_config_filename: str = None,
        query: str = None,
        keywords: List[str] = None,
        hashtags: List[str] = None,
        usernames: List[str] = None,
        operators: Optional[List[str]] = DEFAULT_OPERATORS,
        since_id: Optional[int] = None,
        until_id: Optional[int] = None,
        # 10d
        # 15m
        lookup_period: str = None,
        tweet_fields: Optional[List[str]] = DEFAULT_TWEET_FIELDS,
        user_fields: Optional[List[str]] = DEFAULT_USER_FIELDS,
        expansions: Optional[List[str]] = DEFAULT_EXPANSIONS,
        place_fields: Optional[List[str]] = DEFAULT_PLACE_FIELDS,
        max_tweets: int = DEFAULT_MAX_TWEETS,
    ):
        self.twitter_config_filename = twitter_config_filename

        self.query = query
        self.keywords = keywords
        self.hashtags = hashtags
        self.usernames = usernames
        self.operators = operators

        self.since_id = since_id
        self.until_id = until_id
        self.lookup_period = lookup_period

        self.tweet_fields = tweet_fields
        self.user_fields = user_fields
        self.expansions = expansions
        self.place_fields = place_fields
        self.max_tweets = max_tweets
