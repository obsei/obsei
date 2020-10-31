from typing import List, Optional

from socialtracker.source.base_source_config import BaseSourceConfig


class TwitterSourceConfig(BaseSourceConfig):
    def __init__(
        self,
        twitter_config_filename: str = None,
        query: str = None,
        keywords: List[str] = None,
        hashtags: List[str] = None,
        usernames: List[str] = None,
        operators: List[str] = None,
        since_id: Optional[int] = None,
        until_id: Optional[int] = None,
        # 10d
        # 15m
        lookup_period: str = None,
        tweet_fields: List[str] = None,
        user_fields: List[str] = None,
        expansions: List[str] = None,
        place_fields: List[str] = None,
        max_tweets: Optional[int] = None,
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
