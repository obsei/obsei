import json
import logging
import textwrap
from copy import deepcopy
from typing import Any, Dict, List, Optional

from atlassian import Jira

from obsei.sink.base_sink import BaseSink, BaseSinkConfig, Convertor
from obsei.text_analyzer import AnalyzerResponse

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
    def __init__(
        self,
        url: str,
        username: str,
        password: str,
        issue_type: Dict[str, str],
        project: Dict[str, str],
        verify_ssl: bool = True,
        summary_max_length: int = 50,
        convertor: Convertor = JiraPayloadConvertor(),
    ):
        self.jira = Jira(
            url=url,
            username=username,
            password=password,
            verify_ssl=verify_ssl,
        )
        self.issue_type = issue_type
        self.project = project
        self.summary_max_length = summary_max_length
        super(JiraSinkConfig, self).__init__(convertor)

    @classmethod
    def from_dict(cls, config: Dict[str, Any]):
        return cls(
            url=config["url"],
            username=config["username"],
            password=config["password"],
            issue_type=config["issue_type"],
            project=config["project"],
            convertor=config["convertor"] if "convertor" in config else JiraPayloadConvertor(),
            verify_ssl=config["verify_ssl"] if "verify_ssl" in config else True,
            summary_max_length=config["summary_max_length"] if "summary_max_length" in config else 50,
        )


class JiraSink(BaseSink):
    def send_data(self, analyzer_responses: List[AnalyzerResponse], config: JiraSinkConfig):
        responses = []
        payloads = []
        for analyzer_response in analyzer_responses:
            payloads.append(config.convertor.convert(
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
