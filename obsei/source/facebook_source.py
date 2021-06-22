import logging
from typing import Any, List, Optional

from pydantic import BaseSettings, Field
from pydantic.types import SecretStr
from pyfacebook import Api

from obsei.misc.utils import obj_to_json
from obsei.payload import TextPayload
from obsei.source.base_source import BaseSource, BaseSourceConfig

logger = logging.getLogger(__name__)


class FacebookCredentials(BaseSettings):
    app_id: Optional[SecretStr] = Field(None, env="facebook_app_id")
    app_secret: Optional[SecretStr] = Field(None, env="facebook_app_secret")
    long_term_token: Optional[SecretStr] = Field(None, env="long_term_token")
    api: Optional[Api] = None

    def __init__(self, **data: Any):
        super().__init__(**data)
        if self.app_id is None or self.app_secret is None or self.long_term_token is None:
            raise AttributeError(
                "app and token required to connect to Facebook"
            )

    def get_facebook_api(self):
        if self.api is None:
            self.api = Api(app_id=self.app_id.get_secret_value(),
                           app_secret=self.app_secret.get_secret_value(),
                           long_term_token=self.long_term_token.get_secret_value())
        return self.api

    class Config:
        arbitrary_types_allowed = True


class FacebookSourceConfig(BaseSourceConfig):
    TYPE: str = "Facebook"
    credential: FacebookCredentials = Field(FacebookCredentials())
    page_id: str = None
    since_time: str = None,
    until_time: str = None,
    count: int = 10,
    include_title_description: bool = False,
    include_comments: bool = False


class FacebookSource(BaseSource):
    NAME: str = "Facebook"

    def lookup(self, config: FacebookSourceConfig, **kwargs) -> List[TextPayload]:
        text_payloads: List[TextPayload] = []

        if config.page_id is None:
            raise ValueError("page_id is mandatory")

        api = config.credential.get_facebook_api()
        token_info = api.get_token_info()
        log_object("Token: ", token_info)

        posts = api.get_page_posts(page_id=config.page_id, return_json=True, count=10,
                                   since_time=config.since_time, until_time=config.until_time)
        log_object("Posts: ", str(posts))

        if config.include_comments:
            for post in posts:
                comments = api.get_comments_by_object(object_id=post['id'], return_json=True, filter_type='stream')
                log_object("Comments: ", str(comments))
                payloads = [TextPayload(processed_text=comment['message'], meta=comment, source_name=self.NAME)
                            for comment in comments[0]]
                text_payloads.extend(payloads)

        if config.include_title_description:
            payloads = [TextPayload(
                processed_text=f"{data['title']}. {data['description']}",
                meta=data,
                source_name=self.NAME,
            ) for post in posts for data in post['attachments']['data']]

            text_payloads.extend(payloads)

        return text_payloads


def log_object(message, result):
    logger.debug(message + str(obj_to_json(result)))
