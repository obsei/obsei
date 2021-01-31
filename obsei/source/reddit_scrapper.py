import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

import mmh3
from reddit_rss_reader.reader import RedditContent, RedditRSSReader

from obsei.source.base_source import BaseSource, BaseSourceConfig
from obsei.analyzer.base_analyzer import AnalyzerRequest
from obsei.misc.utils import DATETIME_STRING_PATTERN, DEFAULT_LOOKUP_PERIOD, convert_utc_time

logger = logging.getLogger(__name__)


class RedditScrapperConfig(BaseSourceConfig):
    __slots__ = ('_scrappers',)
    TYPE: str = "RedditScrapper"
    urls: List[str]
    user_agent: Optional[str] = None
    lookup_period: Optional[str] = None

    def __init__(self, **data: Any):
        super().__init__(**data)

        # Using 32 bit hash
        scrappers: Dict[str, RedditRSSReader] = dict()
        for url in self.urls:
            url_hash = '{:02x}'.format(mmh3.hash(url, signed=False))
            scrappers[url_hash] = RedditRSSReader(
                url=url,
                user_agent=self.user_agent if self.user_agent else 'testscript {url_hash}'.format(url_hash=url_hash)
            )
        object.__setattr__(
            self,
            '_scrappers',
            scrappers
        )

    def get_readers(self) -> Dict[str, RedditRSSReader]:
        return self._scrappers


class RedditScrapperSource(BaseSource):
    NAME: Optional[str] = "RedditScrapper"

    def lookup(self, config: RedditScrapperConfig, **kwargs) -> List[AnalyzerRequest]:
        source_responses: List[AnalyzerRequest] = []

        # Get data from state
        id: str = kwargs.get("id", None)
        state: Dict[str, Any] = None if id is None else self.store.get_source_state(id)
        update_state: bool = True if id else False
        state = state or dict()

        for scrapper_id, scrapper in config.get_readers().items():
            scrapper_stat: Dict[str, Any] = state.get(scrapper_id, dict())
            lookup_period: str = scrapper_stat.get(
                "since_time",
                config.lookup_period
            )
            lookup_period = lookup_period or DEFAULT_LOOKUP_PERIOD
            if len(lookup_period) <= 5:
                since_time = convert_utc_time(lookup_period)
            else:
                since_time = datetime.strptime(lookup_period, DATETIME_STRING_PATTERN)

            last_since_time: datetime = since_time

            since_id: Optional[str] = scrapper_stat.get("since_id", None)
            last_index = since_id
            state[scrapper_id] = scrapper_stat

            reddit_data: Optional[List[RedditContent]] = None
            try:
                reddit_data = scrapper.fetch_content(
                    after=since_time,
                    since_id=since_id
                )
            except RuntimeError as ex:
                logger.warning(ex.__cause__)

            reddit_data = reddit_data or []

            for reddit in reddit_data:
                source_responses.append(AnalyzerRequest(
                        processed_text=f"{reddit.title}. {reddit.extracted_text}",
                        meta=reddit.__dict__,
                        source_name=self.NAME
                    )
                )

                if last_since_time is None or last_since_time < reddit.updated:
                    last_since_time = reddit.updated
                if last_index is None:
                    # Assuming list is sorted based on time
                    last_index = reddit.id

            scrapper_stat["since_time"] = last_since_time.strftime(DATETIME_STRING_PATTERN)
            scrapper_stat["since_id"] = last_index

        if update_state:
            self.store.update_source_state(workflow_id=id, state=state)

        return source_responses
