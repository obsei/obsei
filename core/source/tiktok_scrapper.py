import logging, datetime, pytz, asyncio
from typing import Optional, List, Any, Dict
from core.misc.utils import DEFAULT_LOOKUP_PERIOD, convert_utc_time, DATETIME_STRING_PATTERN
from core.payload import TextPayload
from core.source.base_source import BaseSource, BaseSourceConfig
from core.misc.tiktok_comments_scrapper import TiktokCommentsScrapper
from database import *

logger = logging.getLogger(__name__)


class TiktokScrapperConfig(BaseSourceConfig):
    keywords: Optional[list] = None
    ms_token: Optional[str] = None
    video_url: Optional[str] = None
    max_comments: Optional[int] = 20
    max_videos: Optional[int] = 20
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
        isSuccess = False

        try:
            if not config.video_url:
                raise RuntimeError("`video_url` in config should not be empty or None")

            if not config.ms_token:
                raise RuntimeError("`ms_token` in config should not be empty or None")

            scrapper: TiktokCommentsScrapper = TiktokCommentsScrapper(
                ms_token=config.ms_token,
                video_url=config.video_url,
                max_comments=config.max_comments,
            )

            isSuccess = asyncio.run(scrapper.fetch_tiktok_comments(until_datetime=since_time))

        except RuntimeError as ex:
            logger.warning(ex.__cause__)

            
        if isSuccess is True:
            comments = database.tiktok_listeners.find({'original_video_url': config.video_url}, {'_id': False})
            for comment in comments:
                comment = self.flatten_specific_key(comment, '', ['share_info' ,'avatar_thumb', 'text_extra'])

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
                    last_index = comment["cid"]

            state["since_time"] = last_since_time.strftime(DATETIME_STRING_PATTERN)
            state["since_id"] = last_index

            if update_state and self.store is not None:
                self.store.update_source_state(workflow_id=identifier, state=state)

        return source_responses

    def flatten_specific_key(self, obj, prefix='', exclude_key=[]):
        flat_dict = {}
        for key, value in obj.items():
            if key in exclude_key:  # Exclude specified key
                continue

            if isinstance(value, dict):
                if key == 'user':
                    flat_dict.update(self.flatten_specific_key(value, prefix, exclude_key))
                else:
                    flat_dict.update(self.flatten_specific_key(value, prefix + key + '.', exclude_key))
            else:
                flat_dict[prefix + key] = value
        return flat_dict

