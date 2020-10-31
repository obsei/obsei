from typing import List, Optional

from socialtracker.source.base_source_config import BaseSourceConfig


class TwitterSourceConfig(BaseSourceConfig):
    def __init__(
        self,
        consumer_key: str,
        consumer_secret: str,
        account_type: Optional[str] = None,
        bearer_token: Optional[str] = None,
        endpoint: Optional[str] = None,
        query: Optional[str] = None,
        keywords: Optional[List[str]] = None,
        hashtags: Optional[List[str]] = None,
        usernames: Optional[List[str]] = None,
        operators: Optional[List[str]] = None,
        since_id: Optional[int] = None,
        until_id: Optional[int] = None,
        lookup_period_in_sec: Optional[int] = None,
        tweet_fields: Optional[List[str]] = None,
        user_fields: Optional[List[str]] = None,
        expansions: Optional[List[str]] = None,
        place_fields: Optional[List[str]] = None,
        max_tweets: Optional[int] = None,
    ):
        self.consumer_key = consumer_key
        self.consumer_secret = consumer_secret
        self.account_type = account_type
        self.bearer_token = bearer_token
        self.endpoint = endpoint

        self.query = query
        self.keywords = keywords
        self.hashtags = hashtags
        self.usernames = usernames
        self.operators = operators

        self.since_id = since_id
        self.until_id = until_id
        self.lookup_period_in_sec = lookup_period_in_sec

        self.tweet_fields = tweet_fields
        self.user_fields = user_fields
        self.expansions = expansions
        self.place_fields = place_fields
        self.max_tweets = max_tweets
