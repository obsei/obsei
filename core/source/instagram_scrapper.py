import logging, datetime, pytz
from typing import Optional, List, Any, Dict
from core.misc.utils import DEFAULT_LOOKUP_PERIOD, convert_utc_time, DATETIME_STRING_PATTERN
from core.payload import TextPayload
from core.source.base_source import BaseSource, BaseSourceConfig
import instaloader

logger = logging.getLogger(__name__)


class InstagramScrapperConfig(BaseSourceConfig):
    urls: Optional[str] = None
    max_comments: Optional[int] = 20
    lookup_period: Optional[str] = None

    def __init__(self, **data: Any):
        super().__init__(**data)

        if not self.urls:
            raise ValueError("`urls` is required")


class InstagramScrapperSource(BaseSource):
    NAME: Optional[str] = "InstagramScrapper"

    def lookup(self, config: InstagramScrapperConfig, **kwargs: Any) -> List[TextPayload]:  # type: ignore[override]
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
            since_time = datetime.datetime(lookup_period, DATETIME_STRING_PATTERN)

        last_since_time: datetime = since_time
        since_id: Optional[str] = state.get("since_id", None)
        last_index = since_id

        comments: Optional[List[Dict[str, Any]]] = None

        try:
            if not config.urls:
                raise RuntimeError("`url` in config should not be empty or None")

            if not config.urls.split('/')[4]:
                return []
            shortcode = config.urls.split('/')[4]
            loader = self.login_to_instagram()

            if loader is None:
                return []

            post = instaloader.Post.from_shortcode(loader.context, shortcode)
            comments = []

            for comment in post.get_comments():
                comment_time = comment.created_at_utc.replace(tzinfo=pytz.UTC)

                if since_time and comment_time < since_time or len(comments) == int(config.max_comments):
                    continue

                reply_comments = []
                for reply in comment.answers:
                    reply_comments.append(
                        {
                            'comment_id': reply.id,
                            'comment_time': reply.created_at_utc,
                            'comment_text': reply.text,
                            'comment_likes_count': reply.likes_count,
                            'comment_username': reply.owner.username,
                            'comment_user_id': reply.owner.userid,
                            'comment_parent_id': comment.id,
                        }
                    )
                comments.append({
                    'comment_id': comment.id,
                    'comment_time': comment.created_at_utc,
                    'comment_text': comment.text,
                    'comment_likes_count': comment.likes_count,
                    'comment_username': comment.owner.username,
                    'comment_user_id': comment.owner.userid,
                    'comment_parent_id': 0,
                    'answers': reply_comments,
                })

            answers = []
            for item in comments:
                answers.append(item['answers'])
                del item['answers']

            comments = comments + answers
            comments = self.flatten_recursive(comments)

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

    def login_to_instagram(self):
        loader = instaloader.Instaloader()

        try:
            loader.login('----', '----')
            print("Login successful!")
            return loader
        except instaloader.exceptions.BadCredentialsException:
            print("Invalid login credentials!")
            return None

    def flatten_recursive(self, lst):
        result = []
        for item in lst:
            if isinstance(item, list):
                result.extend(self.flatten_recursive(item))
            else:
                result.append(item)
        return result
