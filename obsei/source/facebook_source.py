import logging
from datetime import datetime
from time import mktime
from typing import Any, Dict, List, Optional

from pydantic import BaseSettings, Field, PrivateAttr
from pydantic.types import SecretStr
from pyfacebook import Api

from obsei.misc.utils import DATETIME_STRING_PATTERN, DEFAULT_LOOKUP_PERIOD, convert_utc_time, obj_to_json
from obsei.payload import TextPayload
from obsei.source.base_source import BaseSource, BaseSourceConfig

logger = logging.getLogger(__name__)


class FacebookCredentials(BaseSettings):
    app_id: SecretStr = Field(None, env="facebook_app_id")
    app_secret: SecretStr = Field(None, env="facebook_app_secret")
    long_term_token: SecretStr = Field(None, env="facebook_long_term_token")

    def __init__(self, **data: Any):
        super().__init__(**data)
        if (
            self.app_id is None
            or self.app_secret is None
            or self.long_term_token is None
        ):
            raise AttributeError("app and token required to connect to Facebook")

    class Config:
        arbitrary_types_allowed = True


class FacebookSourceConfig(BaseSourceConfig):
    _api_client: Api = PrivateAttr()
    TYPE: str = "Facebook"
    page_id: str
    post_ids: Optional[List[str]] = None
    lookup_period: Optional[str] = None
    max_post: Optional[int] = 50
    cred_info: FacebookCredentials = Field(FacebookCredentials())

    def __init__(self, **data: Any):
        super().__init__(**data)

        self._api_client = Api(
            app_id=self.cred_info.app_id.get_secret_value(),
            app_secret=self.cred_info.app_secret.get_secret_value(),
            long_term_token=self.cred_info.long_term_token.get_secret_value(),
        )

    def get_client(self) -> Api:
        return self._api_client


class FacebookSource(BaseSource):
    NAME: str = "Facebook"

    def lookup(self, config: FacebookSourceConfig, **kwargs) -> List[TextPayload]:  # type: ignore[override]
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
        since_timestamp: Optional[int] = state.get("since_timestamp", None)
        if since_timestamp is None:
            lookup_period = config.lookup_period or DEFAULT_LOOKUP_PERIOD
            if len(lookup_period) <= 5:
                since_time = convert_utc_time(lookup_period)
            else:
                since_time = datetime.strptime(lookup_period, DATETIME_STRING_PATTERN)

            since_timestamp = int(mktime(since_time.timetuple()))
        post_last_since_time = since_timestamp

        api = config.get_client()
        post_ids = config.post_ids
        if not post_ids:
            posts = api.get_page_posts(
                page_id=config.page_id,
                count=config.max_post,
                since_time=str(since_timestamp),
            )
            self.log_object("Posts: ", str(posts))
            post_ids = []
            for post in posts:
                post_update_time = int(post.updated_time)
                if post_update_time < since_timestamp:
                    break

                if post_last_since_time is None or post_last_since_time < post_update_time:
                    post_last_since_time = post_update_time

                post_ids.append(post.id)

        for post_id in post_ids:
            # Collect post state
            post_stat: Dict[str, Any] = state.get(post_id, dict())
            state[post_id] = post_stat

            comment_since_time = state.get("since_timestamp", since_timestamp)
            comment_last_since_time = comment_since_time

            comments, comment_summary = api.get_comments_by_object(
                object_id=post_id,
                filter_type="stream",
                order_type="reverse_chronological",
            )
            self.log_object("Comments: ", str(comments))
            self.log_object("Comment Summary: ", str(comment_summary))

            for comment in comments:
                comment_created_time = int(comment.created_time)
                if comment_created_time < comment_since_time:
                    break

                if comment_last_since_time is None or comment_last_since_time < comment_created_time:
                    comment_last_since_time = comment_created_time

                source_responses.append(
                    TextPayload(
                        processed_text=comment.message,
                        meta=vars(comment),
                        source_name=self.NAME,
                    )
                )

            post_stat["since_timestamp"] = comment_last_since_time

        state["since_timestamp"] = post_last_since_time

        # TODO: See how to augment with with comments data
        # if config.include_title_description:
        #     text_payloads = [
        #         TextPayload(
        #             processed_text=f"{data['title']}. {data['description']}",
        #             meta=data,
        #             source_name=self.NAME,
        #         )
        #         for post in posts
        #         for data in post["attachments"]["data"]
        #     ]
        #
        #     source_responses.extend(text_payloads)

        if update_state and self.store is not None:
            self.store.update_source_state(workflow_id=id, state=state)

        return source_responses

    @staticmethod
    def log_object(message, result):
        logger.debug(message + str(obj_to_json(result)))
