from datetime import datetime
from typing import Any, Dict, List, Optional

from praw import Reddit
from pydantic import BaseSettings, Field, PrivateAttr, SecretStr

from obsei.payload import TextPayload
from obsei.misc.utils import (
    DATETIME_STRING_PATTERN,
    DEFAULT_LOOKUP_PERIOD,
    convert_utc_time,
    text_from_html,
)
from obsei.source.base_source import BaseSource, BaseSourceConfig


class RedditCredInfo(BaseSettings):
    # Create credential at https://www.reddit.com/prefs/apps
    # Also refer https://praw.readthedocs.io/en/latest/getting_started/authentication.html
    # Currently Password Flow, Read Only Mode and Saved Refresh Token Mode are supported
    client_id: SecretStr = Field(None, env="reddit_client_id")
    client_secret: SecretStr = Field(None, env="reddit_client_secret")
    user_agent: str = "Test User Agent"
    redirect_uri: Optional[str] = None
    refresh_token: Optional[SecretStr] = Field(None, env="reddit_refresh_token")
    username: Optional[str] = Field(None, env="reddit_username")
    password: Optional[SecretStr] = Field(None, env="reddit_password")
    read_only: bool = True


class RedditConfig(BaseSourceConfig):
    # This is done to avoid exposing member to API response
    _reddit_client: Reddit = PrivateAttr()
    TYPE: str = "Reddit"
    subreddits: List[str]
    post_ids: Optional[List[str]] = None
    lookup_period: Optional[str] = None
    include_post_meta: Optional[bool] = True
    post_meta_field: str = "post_meta"
    cred_info: Optional[RedditCredInfo] = Field(None)

    def __init__(self, **data: Any):
        super().__init__(**data)

        self.cred_info = self.cred_info or RedditCredInfo()

        self._reddit_client = Reddit(
            client_id=self.cred_info.client_id.get_secret_value(),
            client_secret=self.cred_info.client_secret.get_secret_value(),
            redirect_uri=self.cred_info.redirect_uri,
            user_agent=self.cred_info.user_agent,
            refresh_token=self.cred_info.refresh_token.get_secret_value()
            if self.cred_info.refresh_token
            else None,
            username=self.cred_info.username if self.cred_info.username else None,
            password=self.cred_info.password.get_secret_value()
            if self.cred_info.password
            else None,
        )

        self._reddit_client.read_only = self.cred_info.read_only

    def get_reddit_client(self) -> Reddit:
        return self._reddit_client


class RedditSource(BaseSource):
    NAME: str = "Reddit"

    def lookup(self, config: RedditConfig, **kwargs) -> List[TextPayload]:  # type: ignore[override]
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

        subreddit_reference = config.get_reddit_client().subreddit(
            "+".join(config.subreddits)
        )
        post_stream = subreddit_reference.stream.submissions(pause_after=-1)
        for post in post_stream:
            if post is None:
                break

            post_data = vars(post)
            post_id = post_data["id"]
            if config.post_ids and not config.post_ids.__contains__(post_id):
                continue

            post_stat: Dict[str, Any] = state.get(post_id, dict())
            lookup_period: str = post_stat.get("since_time", config.lookup_period)
            lookup_period = lookup_period or DEFAULT_LOOKUP_PERIOD
            if len(lookup_period) <= 5:
                since_time = convert_utc_time(lookup_period)
            else:
                since_time = datetime.strptime(lookup_period, DATETIME_STRING_PATTERN)

            last_since_time: datetime = since_time

            since_id: Optional[str] = post_stat.get("since_comment_id", None)
            last_index = since_id
            state[post_id] = post_stat

            post.comment_sort = "new"
            post.comments.replace_more(limit=None)

            # top_level_comments only
            first_comment = True
            for comment in post.comments:
                comment_data = vars(comment)
                if config.include_post_meta:
                    comment_data[config.post_meta_field] = post_data

                comment_time = datetime.utcfromtimestamp(
                    int(comment_data["created_utc"])
                )
                comment_id = comment_data["id"]

                if comment_time < since_time:
                    break
                if last_index and last_index == comment_id:
                    break
                if last_since_time is None or last_since_time < comment_time:
                    last_since_time = comment_time
                if last_index is None or first_comment:
                    last_index = comment_id
                    first_comment = False

                text = "".join(text_from_html(comment_data["body_html"]))

                source_responses.append(
                    TextPayload(
                        processed_text=text, meta=comment_data, source_name=self.NAME
                    )
                )

            post_stat["since_time"] = last_since_time.strftime(DATETIME_STRING_PATTERN)
            post_stat["since_comment_id"] = last_index

        if update_state and self.store is not None:
            self.store.update_source_state(workflow_id=id, state=state)

        return source_responses
