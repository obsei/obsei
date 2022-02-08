import logging
from datetime import datetime

from pydantic import PrivateAttr
from typing import Optional, List, Any, Dict

from obsei.misc.utils import DEFAULT_LOOKUP_PERIOD, convert_utc_time, DATETIME_STRING_PATTERN
from obsei.misc.youtube_reviews_scrapper import YouTubeCommentExtractor
from obsei.payload import TextPayload
from obsei.source.base_source import BaseSource, BaseSourceConfig

logger = logging.getLogger(__name__)


class YoutubeScrapperConfig(BaseSourceConfig):
    _YT_VIDEO_URL: str = PrivateAttr('https://www.youtube.com/watch?v={video_id}')
    TYPE: str = "YoutubeScrapper"
    video_id: Optional[str] = None
    video_url: Optional[str] = None
    user_agent: str = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/79.0.3945.130 Safari/537.36'
    sort_by: int = 1  # 0 = sort by popular, 1 = sort by recent
    max_comments: Optional[int] = 20
    fetch_replies: bool = False
    lang_code: Optional[str] = None
    sleep_time: float = 0.1
    request_retries: int = 5
    lookup_period: Optional[str] = None

    def __init__(self, **data: Any):
        super().__init__(**data)

        if not self.video_id and not self.video_url:
            raise ValueError("Either `video_id` or `video_url` is required")

        if not self.video_url:
            self.video_url = self._YT_VIDEO_URL.format(video_id=self.video_id)


class YoutubeScrapperSource(BaseSource):
    NAME: Optional[str] = "YoutubeScrapper"

    def lookup(self, config: YoutubeScrapperConfig, **kwargs) -> List[TextPayload]:  # type: ignore[override]
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

            scrapper = YouTubeCommentExtractor(
                video_url=config.video_url,
                user_agent=config.user_agent,
                sort_by=config.sort_by,
                max_comments=config.max_comments,
                fetch_replies=config.fetch_replies,
                lang_code=config.lang_code,
                sleep_time=config.sleep_time,
                request_retries=config.request_retries,
            )

            comments = scrapper.fetch_comments(until_datetime=since_time)
        except RuntimeError as ex:
            logger.warning(ex.__cause__)

        comments = comments or []

        for comment in comments:
            source_responses.append(
                TextPayload(
                    processed_text=comment["text"],
                    meta=comment,
                    source_name=self.NAME,
                )
            )

            comment_time = comment["time"]

            if last_since_time is None or last_since_time < comment_time:
                last_since_time = comment_time
            if last_index is None:
                # Assuming list is sorted based on time
                last_index = comment["comment_id"]

        state["since_time"] = last_since_time.strftime(DATETIME_STRING_PATTERN)
        state["since_id"] = last_index

        if update_state and self.store is not None:
            self.store.update_source_state(workflow_id=identifier, state=state)

        return source_responses
