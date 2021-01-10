from datetime import datetime
from typing import Any, Dict, List, Optional

from obsei.misc.appstore_review_reader import AppStoreReviewsReader
from obsei.source.base_source import BaseSource, BaseSourceConfig
from obsei.analyzer.text_analyzer import AnalyzerRequest
from obsei.misc.utils import DATETIME_STRING_PATTERN, convert_utc_time


class AppStoreScrapperConfig(BaseSourceConfig):
    __slots__ = ('_scrappers',)
    TYPE: str = "AppStoreScrapper"
    countries: List[str]
    app_id: str
    lookup_period: Optional[str] = None

    def __init__(self, **data: Any):
        super().__init__(**data)

        scrappers: List[AppStoreReviewsReader] = []
        for country in self.countries:
            scrappers.append(
                AppStoreReviewsReader(
                    country=country,
                    app_id=self.app_id
                )
            )
        object.__setattr__(
            self,
            '_scrappers',
            scrappers
        )

    def get_review_readers(self) -> List[AppStoreReviewsReader]:
        return self._scrappers


class AppStoreScrapperSource(BaseSource):
    NAME: Optional[str] = "AppStoreScrapper"

    def lookup(self, config: AppStoreScrapperConfig, **kwargs) -> List[AnalyzerRequest]:
        source_responses: List[AnalyzerRequest] = []

        # Get data from state
        id: str = kwargs.get("id", None)
        state: Dict[str, Any] = None if id is None else self.store.get_source_state(id)
        update_state: bool = True if id else False
        state = state or dict()

        for scrapper in config.get_review_readers():
            country_stat: Dict[str, Any] = state.get(scrapper.country, dict())
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

            since_id: Optional[str] = country_stat.get("since_id", None)
            last_index = since_id
            state[scrapper.country] = country_stat

            reviews = scrapper.fetch_reviews(
                after=since_time,
                since_id=since_id
            )
            reviews = reviews or []

            for review in reviews:
                source_responses.append(AnalyzerRequest(
                        processed_text=f"{review.title}. {review.content}",
                        meta=review.__dict__,
                        source_name=self.NAME
                    )
                )

                if last_since_time is None or last_since_time < review.date:
                    last_since_time = review.date
                if last_index is None or last_index < review.id:
                    last_index = review.id

            country_stat["since_time"] = last_since_time.strftime(DATETIME_STRING_PATTERN)
            country_stat["since_id"] = last_index

        if update_state:
            self.store.update_source_state(workflow_id=id, state=state)

        return source_responses
