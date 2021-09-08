import logging
import textwrap
from copy import deepcopy
from typing import Any, Dict, List, Mapping, Optional

from pydantic import BaseModel, Field, PrivateAttr, SecretStr
from zenpy import Zenpy
from zenpy.lib.api_objects import Ticket

from obsei.sink.base_sink import BaseSink, BaseSinkConfig, Convertor
from obsei.payload import TextPayload
from obsei.misc.utils import obj_to_markdown

logger = logging.getLogger(__name__)


class ZendeskPayloadConvertor(Convertor):
    def convert(
        self,
        analyzer_response: TextPayload,
        base_payload: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> dict:
        summary_max_length = kwargs.get("summary_max_length", 50)

        payload = base_payload or dict()
        payload["description"] = obj_to_markdown(
            obj=analyzer_response,
            str_enclose_start="{quote}",
            str_enclose_end="{quote}",
        )
        payload["subject"] = textwrap.shorten(
            text=analyzer_response.processed_text, width=summary_max_length
        )

        if analyzer_response.segmented_data is not None and isinstance(
            analyzer_response.segmented_data, Mapping
        ):
            labels_count = kwargs.get("labels_count", 1)
            labels = [
                v
                for k, v in sorted(
                    analyzer_response.segmented_data.items(), key=lambda item: item[1]
                )
            ]
            payload["tags"] = [label for label in labels[:labels_count]]

        return payload


class ZendeskCredInfo(BaseModel):
    email: Optional[str] = Field(None, env="zendesk_email")
    password: Optional[SecretStr] = Field(None, env="zendesk_password")
    oauth_token: Optional[SecretStr] = Field(None, env="zendesk_oauth_token")
    token: Optional[SecretStr] = Field(None, env="zendesk_token")


class ZendeskSinkConfig(BaseSinkConfig):
    # This is done to avoid exposing member to API response
    _client: Zenpy = PrivateAttr()
    TYPE: str = "Zendesk"
    # For custom domain refer http://docs.facetoe.com.au/zenpy.html#custom-domains
    # Mainly you can do this by setting the environment variables:
    # ZENPY_FORCE_NETLOC
    # ZENPY_FORCE_SCHEME (default to https)
    # when set it will force request on:
    # {scheme}://{netloc}/endpoint
    domain: str = Field("zendesk.com")
    subdomain: Optional[str] = Field(None, env="zendesk_subdomain")
    cred_info: Optional[ZendeskCredInfo] = Field(None)
    summary_max_length: int = 50
    labels_count = 3  # Number of labels to fetch
    base_payload: Optional[Dict[str, Any]] = None

    def __init__(self, **data: Any):
        super().__init__(**data)

        self.cred_info = self.cred_info or ZendeskCredInfo()

        self._client = Zenpy(
            domain=self.domain,
            subdomain=self.subdomain,
            email=self.cred_info.email,
            password=None
            if not self.cred_info.password
            else self.cred_info.password.get_secret_value(),
            oauth_token=None
            if not self.cred_info.oauth_token
            else self.cred_info.oauth_token.get_secret_value(),
            token=None
            if not self.cred_info.token
            else self.cred_info.token.get_secret_value(),
        )

    def get_client(self) -> Zenpy:
        return self._client


class ZendeskSink(BaseSink):
    def __init__(self, convertor: Convertor = ZendeskPayloadConvertor(), **data: Any):
        super().__init__(convertor=convertor, **data)

    def send_data(  # type: ignore[override]
        self,
        analyzer_responses: List[TextPayload],
        config: ZendeskSinkConfig,
        **kwargs,
    ):
        responses = []
        payloads = []
        for analyzer_response in analyzer_responses:
            payloads.append(
                self.convertor.convert(
                    analyzer_response=analyzer_response,
                    base_payload=dict()
                    if config.base_payload is None
                    else deepcopy(config.base_payload),
                    summary_max_length=config.summary_max_length,
                    labels_count=config.labels_count,
                )
            )

        for payload in payloads:
            response = config.get_client().tickets.create(Ticket(**payload))
            logger.info(f"response='{response}'")
            responses.append(response)

        return responses
