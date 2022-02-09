import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import mmh3
from pydantic import PrivateAttr
from reddit_rss_reader.reader import RedditContent, RedditRSSReader

from obsei.source.base_source import BaseSource, BaseSourceConfig
from obsei.payload import TextPayload
from obsei.misc.utils import (
    DATETIME_STRING_PATTERN,
    DEFAULT_LOOKUP_PERIOD,
    convert_utc_time,
)

logger = logging.getLogger(__name__)


class RedditScrapperConfig(BaseSourceConfig):
    _scrapper: RedditRSSReader = PrivateAttr()
    TYPE: str = "RedditScrapper"
    url: str
    url_id: Optional[str] = None
    user_agent: Optional[str] = None
    lookup_period: Optional[str] = None

    def __init__(self, **data: Any):
        super().__init__(**data)

        # Using 32 bit hash
        self.url_id = self.url_id or "{:02x}".format(mmh3.hash(self.url, signed=False))

        self._scrapper = RedditRSSReader(
            url=self.url,
            user_agent=self.user_agent
            if self.user_agent
            else "script {url_hash}".format(url_hash=self.url_id),
        )

    def get_readers(self) -> RedditRSSReader:
        return self._scrapper


class RedditScrapperSource(BaseSource):
    NAME: Optional[str] = "RedditScrapper"

    def lookup(self, config: RedditScrapperConfig, **kwargs) -> List[TextPayload]:  # type: ignore[override]
        source_responses: List[TextPayload] = []

        # Get data from state
        identifier: str = kwargs.get("id", None)
        state: Optional[Dict[str, Any]] = (
            None
            if identifier is None or self.store is None
            else self.store.get_source_state(identifier)
        )
        update_state: bool = True if identifier else False
        state = state or dict()

        scrapper_stat: Dict[str, Any] = (
            dict() if not config.url_id else state.get(config.url_id, dict())
        )
        lookup_period: str = scrapper_stat.get("since_time", config.lookup_period)
        lookup_period = lookup_period or DEFAULT_LOOKUP_PERIOD
        if len(lookup_period) <= 5:
            since_time = convert_utc_time(lookup_period)
        else:
            since_time = datetime.strptime(lookup_period, DATETIME_STRING_PATTERN)

        last_since_time: datetime = since_time

        since_id: Optional[str] = scrapper_stat.get("since_id", None)
        last_index = since_id
        if config.url_id:
            state[config.url_id] = scrapper_stat

        reddit_data: Optional[List[RedditContent]] = None
        try:
            reddit_data = config.get_readers().fetch_content(
                after=since_time, since_id=since_id
            )
        except RuntimeError as ex:
            logger.warning(ex.__cause__)

        reddit_data = reddit_data or []

        for reddit in reddit_data:
            source_responses.append(
                TextPayload(
                    processed_text=f"{reddit.title}. {reddit.extracted_text}",
                    meta=reddit.__dict__,
                    source_name=self.NAME,
                )
            )

            comment_time = reddit.updated.replace(tzinfo=timezone.utc)

            if last_since_time is None or last_since_time < comment_time:
                last_since_time = comment_time
            if last_index is None:
                # Assuming list is sorted based on time
                last_index = reddit.id

        scrapper_stat["since_time"] = last_since_time.strftime(DATETIME_STRING_PATTERN)
        scrapper_stat["since_id"] = last_index

        if update_state and self.store is not None:
            self.store.update_source_state(workflow_id=identifier, state=state)

        return source_responses
