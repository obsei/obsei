import logging, datetime, pytz, asyncio
from typing import Optional, List, Any, Dict
from obsei.misc.utils import DEFAULT_LOOKUP_PERIOD, convert_utc_time, DATETIME_STRING_PATTERN
from obsei.payload import TextPayload
from obsei.source.base_source import BaseSource, BaseSourceConfig
from obsei.misc.tiktok_comments_scrapper import TiktokCommentsScrapper

logger = logging.getLogger(__name__)


class TiktokScrapperConfig(BaseSourceConfig):
    video_url: Optional[str] = None
    max_comments: Optional[int] = 20
    lookup_period: Optional[str] = None

    def __init__(self, **data: Any):
        super().__init__(**data)

        if not self.video_url:
            raise ValueError("`video_url` is required")


class TiktokScrapperSource(BaseSource):
    NAME: Optional[str] = "TiktokScrapper"

    def lookup(self, config: TiktokScrapperConfig, **kwargs: Any) -> List[TextPayload]:  # type: ignore[override]
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

        lookup_period: str = state.get("since_time", config.lookup_period)
        lookup_period = lookup_period or DEFAULT_LOOKUP_PERIOD
        if len(lookup_period) <= 5:
            since_time = convert_utc_time(lookup_period)
        else:
            since_time = datetime.strptime(lookup_period, DATETIME_STRING_PATTERN)

        last_since_time: datetime = since_time
        since_id: Optional[str] = state.get("since_id", None)
        last_index = since_id

        comments: Optional[List[Dict[str, Any]]] = None

        try:
            if not config.video_url:
                raise RuntimeError("`video_url` in config should not be empty or None")

            scrapper: TiktokCommentsScrapper = TiktokCommentsScrapper(
                video_url=config.video_url,
                max_comments=config.max_comments,
            )

            comments = asyncio.run(scrapper.fetch_tiktok_comments(until_datetime=since_time))
        except RuntimeError as ex:
            logger.warning(ex.__cause__)

        for comment in comments:
            source_responses.append(
                TextPayload(
                    processed_text=comment['text'],
                    meta=comment,
                    source_name=self.NAME,
                )
            )

            comment_time = float(comment['create_time'])
            comment_time = datetime.datetime.fromtimestamp(comment_time, pytz.UTC)

            if comment_time is not None and (last_since_time is None or last_since_time < comment_time):
                last_since_time = comment_time
            if last_index is None:
                # Assuming list is sorted based on time
                last_index = comment["aweme_id"]

        state["since_time"] = last_since_time.strftime(DATETIME_STRING_PATTERN)
        state["since_id"] = last_index

        if update_state and self.store is not None:
            self.store.update_source_state(workflow_id=identifier, state=state)

        return source_responses
