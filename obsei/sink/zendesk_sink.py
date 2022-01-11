import json
import logging
import textwrap
from copy import deepcopy

import requests
from typing import Any, Dict, List, Mapping, Optional

from pydantic import BaseModel, Field, SecretStr

from obsei.sink.base_sink import BaseSink, BaseSinkConfig, Convertor
from obsei.payload import TextPayload
from obsei.misc.utils import obj_to_markdown

logger = logging.getLogger(__name__)


class ZendeskPayloadConvertor(Convertor):
    # Refer https://developer.zendesk.com/api-reference/ticketing/tickets/tickets/#create-ticket
    # for the payload details
    def convert(
        self,
        analyzer_response: TextPayload,
        base_payload: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> dict:
        summary_max_length = kwargs.get("summary_max_length", 50)

        payload = base_payload or dict()

        if "ticket" not in payload:
            payload["ticket"] = dict()

        if "comment" not in payload["ticket"]:
            payload["ticket"]["comment"] = dict()

        # For non-html content, use "body" key
        payload["html_body"] = obj_to_markdown(
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

    def __init__(self, **data: Any):
        super().__init__(**data)

        if not self.oauth_token and not self.token and not self.email and not self.password:
            raise ValueError("At least one credential is required")

        if self.password and self.token:
            raise ValueError("Only one of password or token can be provided")

    def get_session(self) -> requests.Session:
        session = requests.Session()

        if self.oauth_token:
            session.headers.update({"Authorization": f'Bearer {self.oauth_token.get_secret_value()}'})
        elif self.email and self.token:
            session.auth = (f'{self.email}/token', self.token.get_secret_value())
        elif self.email and self.password:
            session.auth = (self.email, self.password.get_secret_value())

        return session


class ZendeskSinkConfig(BaseSinkConfig):
    TYPE: str = "Zendesk"
    ticket_api: str = Field(default="/api/v2/tickets.json")
    scheme: str = Field(default="https", env="zendesk_scheme")
    domain: str = Field(default="zendesk.com", env="zendesk_domain")
    subdomain: Optional[str] = Field(None, env="zendesk_subdomain")
    cred_info: Optional[ZendeskCredInfo] = Field(None)
    summary_max_length: int = 50
    labels_count = 3  # Number of labels to fetch
    base_payload: Optional[Dict[str, Any]] = None

    def __init__(self, **data: Any):
        super().__init__(**data)

        self.cred_info = self.cred_info or ZendeskCredInfo()

    def get_endpoint(self) -> str:
        sub_prefix = "" if self.subdomain is None or self.subdomain is '' else f"/{self.subdomain}."
        return f'{self.scheme}://{sub_prefix}{self.domain}{self.ticket_api}'


class ZendeskSink(BaseSink):
    def __init__(self, convertor: Convertor = ZendeskPayloadConvertor(), **data: Any):
        super().__init__(convertor=convertor, **data)

    def send_data(  # type: ignore[override]
        self,
        analyzer_responses: List[TextPayload],
        config: ZendeskSinkConfig,
        **kwargs,
    ):
        responses: List[Any] = []
        payloads: List[Dict[str, Any]] = []

        if config.cred_info is None:
            logger.error("Zendesk credentials are not provided")
            return responses

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
            session = config.cred_info.get_session()
            response = session.post(
                config.get_endpoint(),
                json=json.dumps(payload["segmented_data"], indent=2, ensure_ascii=False)
            )
            logger.info(f"response='{response}'")
            responses.append(response)

        return responses
