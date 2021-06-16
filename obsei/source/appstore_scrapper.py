import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app_store.app_store_reviews_reader import AppStoreReviewsReader
from pydantic import PrivateAttr

from obsei.misc.web_search import perform_search
from obsei.source.base_source import BaseSource, BaseSourceConfig
from obsei.payload import TextPayload
from obsei.misc.utils import (
    DATETIME_STRING_PATTERN,
    DEFAULT_LOOKUP_PERIOD,
    convert_utc_time,
)


class AppStoreScrapperConfig(BaseSourceConfig):
    _scrappers: List[AppStoreReviewsReader] = PrivateAttr()
    TYPE: str = "AppStoreScrapper"
    countries: List[str]
    app_id: Optional[str] = None
    app_name: Optional[str] = None
    lookup_period: Optional[str] = None
    max_count: Optional[int] = None

    def __init__(self, **data: Any):
        super().__init__(**data)

        if not self.app_id and self.app_name:
            self.app_id = AppStoreScrapperConfig.search_id(self.app_name)

        if not self.app_id:
            raise ValueError("Valid `app_id` or `app_name` is mandatory")

        self._scrappers = []
        for country in self.countries:
            self._scrappers.append(
                AppStoreReviewsReader(country=country, app_id=self.app_id)
            )

    def get_review_readers(self) -> List[AppStoreReviewsReader]:
        return self._scrappers

    # Code is influenced from https://github.com/cowboy-bebug/app-store-scraper
    @classmethod
    def search_id(cls, app_name: str, store: str = "app"):
        if store == "app":
            landing_url = "apps.apple.com"
            request_host = "amp-api.apps.apple.com"
        else:
            landing_url = "podcasts.apple.com"
            request_host = "amp-api.podcasts.apple.com"

        base_request_url = f"https://{request_host}"
        search_response = perform_search(
            request_url=base_request_url, query=f"app store {app_name}"
        )

        pattern = fr"{landing_url}/[a-z]{{2}}/.+?/id([0-9]+)"
        match_object = re.search(pattern, search_response.text)
        if match_object:
            app_id = match_object.group(1)
        else:
            raise RuntimeError("Pattern matching is not found")
        return app_id


class AppStoreScrapperSource(BaseSource):
    NAME: Optional[str] = "AppStoreScrapper"

    def lookup(self, config: AppStoreScrapperConfig, **kwargs) -> List[TextPayload]:  # type: ignore[override]
        source_responses: List[TextPayload] = []

        # Get data from state
        id: str = kwargs.get("id", None)
        state: Optional[Dict[str, Any]] = (
            None
            if id is None or self.store is None
            else self.store.get_source_state(id)
        )
        update_state: bool = True if id else False
        state = state or dict()

        for scrapper in config.get_review_readers():
            country_stat: Dict[str, Any] = state.get(scrapper.country, dict())
            lookup_period: str = country_stat.get("since_time", config.lookup_period)
            lookup_period = lookup_period or DEFAULT_LOOKUP_PERIOD
            if len(lookup_period) <= 5:
                since_time = convert_utc_time(lookup_period)
            else:
                since_time = datetime.strptime(lookup_period, DATETIME_STRING_PATTERN)
                since_time = since_time.replace(tzinfo=timezone.utc)

            last_since_time: datetime = since_time

            since_id: Optional[int] = country_stat.get("since_id", None)
            last_index = since_id
            state[scrapper.country] = country_stat

            reviews = scrapper.fetch_reviews(after=since_time, since_id=since_id)
            reviews = reviews or []
            if config.max_count is not None and config.max_count < len(reviews):
                reviews = reviews[:config.max_count]

            for review in reviews:
                source_responses.append(
                    TextPayload(
                        processed_text=f"{review.title}. {review.content}",
                        meta=vars(review) if hasattr(review, "__dict__") else review,
                        source_name=self.NAME,
                    )
                )

                review_time = review.date.replace(tzinfo=timezone.utc)
                if review_time < since_time:
                    break
                if last_since_time is None or last_since_time < review_time:
                    last_since_time = review_time
                if last_index is None or last_index < review.id:
                    last_index = review.id

            country_stat["since_time"] = last_since_time.strftime(
                DATETIME_STRING_PATTERN
            )
            country_stat["since_id"] = last_index

        if update_state and self.store is not None:
            self.store.update_source_state(workflow_id=id, state=state)

        return source_responses
