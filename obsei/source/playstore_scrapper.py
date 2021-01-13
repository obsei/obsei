from datetime import datetime
from typing import Any, Dict, List, Optional

from google_play_scraper import Sort, reviews

from obsei.source.base_source import BaseSource, BaseSourceConfig
from obsei.analyzer.text_analyzer import AnalyzerRequest
from obsei.misc.utils import DATETIME_STRING_PATTERN, convert_utc_time


class PlayStoreScrapperConfig(BaseSourceConfig):
    TYPE: str = "PlayStoreScrapper"
    countries: List[str]
    package_name: str
    language: Optional[str]
    filter_score_with: Optional[int] = None
    lookup_period: Optional[str] = None

    def __init__(self, **data: Any):
        super().__init__(**data)

        if self.language is None:
            self.language = "en"


class PlayStoreScrapperSource(BaseSource):
    NAME: Optional[str] = "PlayStoreScrapper"

    def lookup(self, config: PlayStoreScrapperConfig, **kwargs) -> List[AnalyzerRequest]:
        source_responses: List[AnalyzerRequest] = []

        # Get data from state
        id: str = kwargs.get("id", None)
        state: Dict[str, Any] = None if id is None else self.store.get_source_state(id)
        update_state: bool = True if id else False
        state = state or dict()

        for country in config.countries:
            country_stat: Dict[str, Any] = state.get(country, dict())
            lookup_period: str = country_stat.get(
                "since_time",
                config.lookup_period
            )
            lookup_period = lookup_period or "1h"
            if len(lookup_period) <= 5:
                since_time = convert_utc_time(lookup_period)
            else:
                since_time = datetime.strptime(lookup_period, DATETIME_STRING_PATTERN)

            last_since_time: datetime = since_time

            # since_id: Optional[str] = country_stat.get("since_id", None)
            # last_index = since_id
            # state[scrapper.country] = country_stat

            store_reviews, continuation_token = reviews(
                app_id=config.package_name,
                lang=config.language,
                country=country,
                sort=Sort.NEWEST,
                filter_score_with=config.filter_score_with
            )
            store_reviews = store_reviews or []

            for review in store_reviews:
                source_responses.append(AnalyzerRequest(
                        processed_text=review["content"],
                        meta=review,
                        source_name=self.NAME
                    )
                )

                if last_since_time is None or last_since_time < review["at"]:
                    last_since_time = review["at"]
                # if last_index is None or last_index < review.id:
                #    last_index = review.id

            country_stat["since_time"] = last_since_time.strftime(DATETIME_STRING_PATTERN)
            # country_stat["since_id"] = last_index

        if update_state:
            self.store.update_source_state(workflow_id=id, state=state)

        return source_responses
