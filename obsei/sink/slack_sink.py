import logging
from typing import Any, List

from pydantic import Field, PrivateAttr, SecretStr
from slack_sdk import WebClient

from obsei.sink.base_sink import BaseSink, BaseSinkConfig, Convertor
from obsei.analyzer.base_analyzer import AnalyzerResponse

logger = logging.getLogger(__name__)


class SlackSinkConfig(BaseSinkConfig):
    # This is done to avoid exposing member to API response
    _slack_client: WebClient = PrivateAttr()
    TYPE: str = "Slack"

    slack_token: SecretStr = Field(None, env='SLACK_TOKEN')
    channel_id: str

    def __init__(self, **data: Any):
        super().__init__(**data)
        self._slack_client=WebClient(token=self.slack_token.get_secret_value())

    def get_slack_client(self):
        return self._slack_client


class SlackSink(BaseSink):
    def __init__(self, **data: Any):
        super().__init__(**data)

    def send_data(
        self,
        analyzer_responses: List[AnalyzerResponse],
        config: SlackSinkConfig,
        **kwargs
    ):
        responses = []
        payloads = []
        for analyzer_response in analyzer_responses:
            payloads.append(self.convertor.convert(
                analyzer_response=analyzer_response
            ))

        for payload in payloads:
            response = config.get_slack_client().chat_postMessage(
                channel=config.channel_id,
                text=f'```\n{payload["processed_text"]}\n```'
            )
            logger.info(f"response='{response}'")
            responses.append(response)

        return responses
