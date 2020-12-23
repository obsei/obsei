import json
import logging
import textwrap
from copy import deepcopy
from typing import Any, Dict, List, Optional

from pydantic import SecretStr

from obsei.sink.base_sink import BaseSink, BaseSinkConfig, Convertor
from obsei.analyzer.text_analyzer import AnalyzerResponse

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
        payload["description"] = str(json.dumps(analyzer_response.to_dict()))
        payload["summary"] = textwrap.shorten(analyzer_response.processed_text, width=summary_max_length)

        return payload


class JiraSinkConfig(BaseSinkConfig):
    TYPE: str = "Jira"
    url: str
    username: SecretStr
    password: SecretStr
    issue_type: Dict[str, str]
    project: Dict[str, str]
    verify_ssl: bool = True
    summary_max_length: int = 50


class JiraSink(BaseSink):
    def __init__(self, convertor: Convertor = JiraPayloadConvertor()):
        super().__init__(convertor)

    def send_data(self, analyzer_responses: List[AnalyzerResponse], config: JiraSinkConfig):
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
            ))

        for payload in payloads:
            response = config.jira.create_issue(fields=payload)
            logger.info(f"response='{response}'")
            responses.append(response)

        return responses
