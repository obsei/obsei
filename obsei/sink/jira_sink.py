import logging
import textwrap
from copy import deepcopy
from typing import Any, Dict, List, Optional

from atlassian import Jira
from pydantic import SecretStr

from obsei.sink.base_sink import BaseSink, BaseSinkConfig, Convertor
from obsei.analyzer.text_analyzer import AnalyzerResponse
from obsei.misc.utils import obj_to_markdown

logger = logging.getLogger(__name__)


class JiraPayloadConvertor(Convertor):
    def convert(
        self,
        analyzer_response: AnalyzerResponse,
        base_payload: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> dict:
        summary_max_length = kwargs.get("summary_max_length", 50)

        payload = deepcopy(base_payload)
        payload["description"] = obj_to_markdown(
            obj=analyzer_response,
            str_enclose_start="{quote}",
            str_enclose_end="{quote}"
        )
        payload["summary"] = textwrap.shorten(
            text=analyzer_response.processed_text,
            width=summary_max_length
        )

        # TODO: Find correct payload to update labels fields
        labels_count = kwargs.get("labels_count", 1)
        # labels = [v for k, v in sorted(analyzer_response.classification.items(), key=lambda item: item[1])]
        # payload['labels'] = [{"name": label} for label in labels[:labels_count]]

        return payload


class JiraSinkConfig(BaseSinkConfig):
    # This is done to avoid exposing member to API response
    __slots__ = ('_jira_client',)
    TYPE: str = "Jira"
    url: str
    username: SecretStr
    password: SecretStr
    issue_type: Dict[str, str]
    project: Dict[str, str]
    update_history: bool = True
    verify_ssl: bool = False
    summary_max_length: int = 50
    labels_count = 2 # Number of labels to fetch

    def __init__(self, **data: Any):
        super().__init__(**data)
        object.__setattr__(
            self,
            '_jira_client',
            Jira(
                url=self.url,
                username=self.username.get_secret_value(),
                password=self.password.get_secret_value(),
                verify_ssl=self.verify_ssl,
            )
        )

    def get_jira_client(self):
        return self._jira_client


class JiraSink(BaseSink):
    def __init__(self, convertor: Convertor = JiraPayloadConvertor()):
        super().__init__(convertor)

    def send_data(
        self,
        analyzer_responses: List[AnalyzerResponse],
        config: JiraSinkConfig,
        **kwargs
    ):
        responses = []
        payloads = []
        for analyzer_response in analyzer_responses:
            payloads.append(self.convertor.convert(
                analyzer_response=analyzer_response,
                base_payload={
                    "project": config.project,
                    "issuetype": config.issue_type,
                },
                summary_max_length=config.summary_max_length,
                labels_count=config.labels_count
            ))

        for payload in payloads:
            response = config.get_jira_client().create_issue(
                fields=payload,
                update_history=config.update_history
            )
            logger.info(f"response='{response}'")
            responses.append(response)

        return responses
