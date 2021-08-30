import logging
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from urllib import parse

from google_play_scraper import Sort, reviews

from obsei.misc.web_search import perform_search
from obsei.source.base_source import BaseSource, BaseSourceConfig
from obsei.payload import TextPayload
from obsei.misc.utils import (
    DATETIME_STRING_PATTERN,
    DEFAULT_LOOKUP_PERIOD,
    convert_utc_time,
)

logger = logging.getLogger(__name__)


class PlayStoreScrapperConfig(BaseSourceConfig):
    TYPE: str = "PlayStoreScrapper"
    app_url: Optional[str] = None
    countries: Optional[List[str]] = None
    package_name: Optional[str] = None
    app_name: Optional[str] = None
    language: Optional[str] = None
    filter_score_with: Optional[int] = None
    lookup_period: Optional[str] = None
    max_count: Optional[int] = 200

    def __init__(self, **data: Any):
        super().__init__(**data)

        if self.app_url is not None:
            self.package_name, self.countries, self.language = PlayStoreScrapperConfig.parse_app_url(self.app_url)
        else:
            if not self.package_name and self.app_name:
                self.package_name = PlayStoreScrapperConfig.search_package_name(
                    self.app_name
                )

        if not self.package_name:
            raise ValueError("Valid `package_name`, `app_name` or `app_url` is mandatory")

        self.language = self.language or "en"
        self.countries = self.countries or ["us"]
        self.app_name = self.app_name or self.package_name

    @classmethod
    def parse_app_url(cls, app_url: str):

        parsed_url = parse.urlparse(app_url)
        query_dict = parse.parse_qs(parsed_url.query)
        countries = query_dict.get('gl', None)

        language = None
        languages = query_dict.get('hl', None)
        if languages is not None:
            language = languages[0]

        package_name = None
        package_ids = query_dict.get('id', None)
        if package_ids is not None:
            package_name = package_ids[0]

        return package_name, countries, language

    @classmethod
    def search_package_name(cls, app_name: str):
        base_request_url = f"https://play.google.com"
        search_response = perform_search(
            request_url=base_request_url, query=f"play store {app_name}"
        )

        pattern = r"play.google.com/store/apps/details.+?id=([0-9a-z.]+)"
        match_object = re.search(pattern, search_response.text)
        if match_object:
            app_id = match_object.group(1)
        else:
            raise RuntimeError("Pattern matching is not found")
        return app_id


class PlayStoreScrapperSource(BaseSource):
    NAME: Optional[str] = "PlayStoreScrapper"

    def lookup(  # type: ignore[override]
        self, config: PlayStoreScrapperConfig, **kwargs
    ) -> List[TextPayload]:
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

        if config.countries is None or len(config.countries) == 0:
            logger.warning("`countries` in config should not be empty or None")
            return source_responses

        for country in config.countries:
            country_stat: Dict[str, Any] = state.get(country, dict())
            lookup_period: str = country_stat.get("since_time", config.lookup_period)
            lookup_period = lookup_period or DEFAULT_LOOKUP_PERIOD
            if len(lookup_period) <= 5:
                since_time = convert_utc_time(lookup_period)
            else:
                since_time = datetime.strptime(lookup_period, DATETIME_STRING_PATTERN)

            last_since_time: datetime = since_time

            # since_id: Optional[str] = country_stat.get("since_id", None)
            # last_index = since_id
            # state[scrapper.country] = country_stat

            continuation_token = None
            while True:
                store_reviews, continuation_token = reviews(
                    app_id=config.package_name,
                    lang=config.language,
                    country=country,
                    sort=Sort.NEWEST,
                    filter_score_with=config.filter_score_with,
                    continuation_token=continuation_token,
                    count=config.max_count,
                )
                store_reviews = store_reviews or []

                for review in store_reviews:
                    source_responses.append(
                        TextPayload(
                            processed_text=review["content"],
                            meta=review,
                            source_name=self.NAME,
                        )
                    )
                    review_time = review["at"].replace(tzinfo=timezone.utc)

                    if since_time > review_time:
                        break

                    if last_since_time is None or last_since_time < review_time:
                        last_since_time = review_time
                    # if last_index is None or last_index < review.id:
                    #    last_index = review.id

                if (
                    continuation_token is None
                    or continuation_token.token is None
                    or continuation_token.count <= len(source_responses)
                ):
                    break

            country_stat["since_time"] = last_since_time.strftime(
                DATETIME_STRING_PATTERN
            )
            # country_stat["since_id"] = last_index

        if update_state and self.store is not None:
            self.store.update_source_state(workflow_id=id, state=state)

        return source_responses
