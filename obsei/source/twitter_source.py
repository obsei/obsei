import logging

from typing import Any, Dict, List

from searchtweets import collect_results, gen_request_parameters, load_credentials

from obsei.source.twitter_source_config import TwitterSourceConfig
from obsei.source.base_source import BaseSource, SourceResponse

import preprocessor as cleaning_processor

logger = logging.getLogger(__name__)


class TwitterSource(BaseSource):

    def lookup(self, config: TwitterSourceConfig) -> List[SourceResponse]:
        if not config.query and not config.keywords and not config.hashtags and config.usernames:
            raise AttributeError("At least one non empty parameter required (query, keywords, hashtags, and usernames)")

        search_args = load_credentials(filename=config.twitter_config_filename, env_overwrite=True)

        place_fields = ",".join(config.place_fields) if config.place_fields is not None else None
        user_fields = ",".join(config.user_fields) if config.user_fields is not None else None
        expansions = ",".join(config.expansions) if config.expansions is not None else None
        tweet_fields = ",".join(config.tweet_fields) if config.tweet_fields is not None else None

        query = self._generate_query_string(
            query=config.query,
            keywords=config.keywords,
            hashtags=config.hashtags,
            usernames=config.usernames,
            operators=config.operators
        )

        search_query = gen_request_parameters(
            query=query,
            results_per_call=config.max_tweets,
            place_fields=place_fields,
            expansions=expansions,
            user_fields=user_fields,
            tweet_fields=tweet_fields,
            since_id=config.since_id,
            until_id=config.until_id,
            start_time=config.lookup_period
        )

        tweets = collect_results(
            query=search_query,
            max_tweets=config.max_tweets,
            result_stream_args=search_args
        )

        source_responses: List[SourceResponse] = []
        next_stats: Dict[str, Any] = None # TODO use it later
        for tweet in tweets:
            if "id" in tweet:
                source_responses.append(TwitterSource.get_source_output(tweet))
            else:
                next_stats = tweet

        logger.info(f"next_stats='{next_stats}'")
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

    @staticmethod
    def get_source_output(tweet: Dict[str, Any]):
        processed_text = cleaning_processor.clean(tweet["text"])
        return SourceResponse(processed_text, tweet)
