import json
import logging
from typing import Any, List, Optional

from pydantic import Field, PrivateAttr, SecretStr
from slack_sdk import WebClient

from obsei.sink.base_sink import BaseSink, BaseSinkConfig
from obsei.payload import TextPayload

logger = logging.getLogger(__name__)


class SlackSinkConfig(BaseSinkConfig):
    # This is done to avoid exposing member to API response
    _slack_client: WebClient = PrivateAttr()
    TYPE: str = "Slack"

    slack_token: Optional[SecretStr] = Field(None, env="slack_token")
    channel_id: Optional[str] = Field(None, env="slack_channel_id")

    def __init__(self, **data: Any):
        super().__init__(**data)
        if self.slack_token is None or self.channel_id:
            raise AttributeError(
                "Slack informer need slack_token and channel_id"
            )

        self._slack_client = WebClient(token=self.slack_token.get_secret_value())

    def get_slack_client(self):
        return self._slack_client


class SlackSink(BaseSink):
    def __init__(self, **data: Any):
        super().__init__(**data)

    def send_data(  # type: ignore[override]
        self,
        analyzer_responses: List[TextPayload],
        config: SlackSinkConfig,
        **kwargs,
    ):
        responses = []
        payloads = []
        for analyzer_response in analyzer_responses:
            payloads.append(self.convertor.convert(analyzer_response=analyzer_response))

        for payload in payloads:
            response = config.get_slack_client().chat_postMessage(
                channel=config.channel_id,
                text=f'Message: `{str(payload["processed_text"])}` '
                f'```{json.dumps(payload["segmented_data"], indent=2, ensure_ascii=False)}```',
            )
            logger.info(f"response='{response}'")
            responses.append(response)

        return responses
