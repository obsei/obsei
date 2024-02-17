import logging, datetime, pytz
from typing import Optional, List, Any, Dict
from core.misc.utils import DEFAULT_LOOKUP_PERIOD, convert_utc_time, DATETIME_STRING_PATTERN
from core.payload import TextPayload
from core.source.base_source import BaseSource, BaseSourceConfig
import facebook_scraper as fs

logger = logging.getLogger(__name__)


class FacebookScrapperConfig(BaseSourceConfig):
    urls: Optional[str] = None
    max_comments: Optional[int] = 20
    lookup_period: Optional[str] = None

    def __init__(self, **data: Any):
        super().__init__(**data)

        if not self.urls:
            raise ValueError("`urls` is required")


class FacebookScrapperSource(BaseSource):
    NAME: Optional[str] = "FacebookScrapper"

    def lookup(self, config: FacebookScrapperConfig, **kwargs: Any) -> List[TextPayload]:  # type: ignore[override]
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
            if not config.urls:
                raise RuntimeError("`url` in config should not be empty or None")

            gen = fs.get_posts(
                post_urls=[config.urls],
                options={"comments": config.max_comments, "progress": True},
                cookies="libs/cookies.txt"
            )

            post = next(gen)
            comment_arr = []
            if 'comments_full' in post: 
                comments = post['comments_full']

                for comment in comments:
                    comment['commment_parent_id'] = 0;
                    reply_comment_arr = []
                    for reply in comment['replies']:
                        reply['commment_parent_id'] = comment['comment_id']
                        del reply['comment_reactors']
                        reply_comment_arr.append(reply)
                    comment_arr.append(reply_comment_arr)
                    del comment['replies']
                    del comment['comment_reactors']

                    comment_arr.append(comment)

            comments = self.flatten_recursive(comment_arr)
        except RuntimeError as ex:
            logger.warning(ex.__cause__)

        for comment in comments:
            source_responses.append(
                TextPayload(
                    processed_text=comment['comment_text'],
                    meta=comment,
                    source_name=self.NAME,
                )
            )

            comment_time = None
            if isinstance(comment['comment_time'], datetime.datetime):
                comment_time = comment['comment_time'].replace(tzinfo=pytz.UTC)

            if comment_time is not None and (last_since_time is None or last_since_time < comment_time):
                last_since_time = comment_time
            if last_index is None:
                last_index = comment['comment_id']

        state["since_time"] = last_since_time.strftime(DATETIME_STRING_PATTERN)
        state["since_id"] = last_index

        if update_state and self.store is not None:
            self.store.update_source_state(workflow_id=identifier, state=state)

        return source_responses

    def flatten_recursive(self, lst):
        result = []
        for item in lst:
            if isinstance(item, list):
                result.extend(self.flatten_recursive(item))
            else:
                result.append(item)
        return result
