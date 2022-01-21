import logging
from datetime import datetime
from typing import Optional, List, Any, Dict

import requests
from pydantic import SecretStr, Field

from obsei.misc.utils import convert_utc_time, DATETIME_STRING_PATTERN
from obsei.payload import TextPayload
from obsei.source.base_source import BaseSourceConfig, BaseSource

logger = logging.getLogger(__name__)
OUTSCRAPPER_API_URL = 'https://api.app.outscraper.com'


class OSGoogleMapsReviewsConfig(BaseSourceConfig):
    NAME: str = "Maps Reviews Scrapper"
    queries: List[str]
    sort: str = "newest"
    ignore_empty_reviews: bool = True
    language: str = "en"
    since_timestamp: Optional[int] = None
    until_timestamp: Optional[int] = None
    lookup_period: Optional[str] = None
    number_of_reviews: int = 10
    number_of_places_per_query: int = 1
    country: Optional[str] = None
    # parameter defines the coordinates of the location where you want your query to be applied.
    # It has to be constructed in the next sequence: "@" + "latitude" + "," + "longitude" + "," + "zoom"
    # (e.g. "@41.3954381,2.1628662,15.1z").
    central_coordinates: Optional[str] = None
    # Get API key from https://outscraper.com/
    api_key: Optional[SecretStr] = Field(None, env="outscrapper_api_key")

    def __init__(self, **values: Any):
        super().__init__(**values)

        if self.api_key is None:
            raise ValueError("OutScrapper API key require to fetch reviews data")


class OSGoogleMapsReviewsSource(BaseSource):
    NAME: str = "Maps Reviews Scrapper"

    def lookup(self, config: OSGoogleMapsReviewsConfig, **kwargs) -> List[TextPayload]:  # type: ignore[override]
        source_responses: List[TextPayload] = []

        # Get data from state
        identifier: str = kwargs.get("id", None)

        state: Optional[Dict[str, Any]] = (
            None
            if id is None or self.store is None
            else self.store.get_source_state(identifier)
        )

        update_state: bool = True if identifier else False
        state = state or dict()

        since_timestamp: Optional[int] = (
            config.since_timestamp or None if state is None else state.get("since_timestamp", None)
        )
        if since_timestamp is None and config.lookup_period is not None:
            if len(config.lookup_period) <= 5:
                since_time = convert_utc_time(config.lookup_period)
            else:
                since_time = datetime.strptime(config.lookup_period, DATETIME_STRING_PATTERN)

            since_timestamp = int(since_time.timestamp())

        last_reviews_since_time = since_timestamp

        params: Dict[str, Any] = {
            'query': config.queries,
            'reviewsLimit': config.number_of_reviews,
            'limit': config.number_of_places_per_query,
            'sort': config.sort,
            'start': since_timestamp,
            'cutoff': config.until_timestamp,
            'ignoreEmpty': config.ignore_empty_reviews,
            'coordinates': config.central_coordinates,
            'language': config.language,
            'region': config.country,
            'async': False,
        }

        response = requests.get(f'{OUTSCRAPPER_API_URL}/maps/reviews-v2', params=params, headers={
            'X-API-KEY': "" if config.api_key is None else config.api_key.get_secret_value(),
        })

        queries_data = []
        if response.status_code == 200:
            queries_data = response.json().get('data', [])
        else:
            logger.warning(f"API call failed with error: {response.json()}")

        for query_data in queries_data:
            reviews = [] if "reviews_data" not in query_data else query_data.pop("reviews_data")

            for review in reviews:
                source_responses.append(
                    TextPayload(
                        processed_text=review["review_text"],
                        meta={**review, **query_data},
                        source_name=self.NAME,
                    )
                )
                review_time = review["review_timestamp"]

                if last_reviews_since_time is None or last_reviews_since_time < review_time:
                    last_reviews_since_time = review_time

        state["since_timestamp"] = last_reviews_since_time
        if update_state and self.store is not None:
            self.store.update_source_state(workflow_id=identifier, state=state)

        return source_responses
