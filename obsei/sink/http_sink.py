from copy import deepcopy
from typing import Any, Dict, List

import logging
import requests

from obsei.sink.base_sink import BaseSink, BaseSinkConfig, Convertor
from obsei.analyzer.text_analyzer import AnalyzerResponse

logger = logging.getLogger(__name__)

DEFAULT_HEADERS = {
    "Content-type": "application/json"
}


class HttpSinkConfig(BaseSinkConfig):
    TYPE: str = "Http"
    url: str
    headers: Dict[str, Any] = None
    base_payload: Dict[str, Any] = None
    # analyzer_output to payload mapping
    payload_mapping: Dict[str, List[str]] = None
    field_conversion: Dict[str, str] = None


class HttpSink(BaseSink):
    def __init__(self, convertor: Convertor = Convertor(), **data: Any):
        super().__init__(convertor=convertor, **data)

    def send_data(
        self,
        analyzer_responses: List[AnalyzerResponse],
        config: HttpSinkConfig,
        **kwargs
    ):

        headers = config.headers or DEFAULT_HEADERS

        payloads = []
        responses = []
        for analyzer_response in analyzer_responses:
            payloads.append(self.convertor.convert(
                analyzer_response=analyzer_response,
                base_payload=deepcopy(config.base_payload)
            ))

        for payload in payloads:
            response = requests.post(
                url=config.url,
                json=payload,
                headers=headers,
            )

            logger.info(f"response='{response.__dict__}'")
            responses.append(response)

        return responses
