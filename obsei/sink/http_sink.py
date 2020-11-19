from copy import deepcopy
from typing import Any, Dict, List

import logging
import requests

from obsei.sink.base_sink import BaseSink, BaseSinkConfig, Convertor
from obsei.text_analyzer import AnalyzerResponse

logger = logging.getLogger(__name__)

DEFAULT_HEADERS = {
    "Content-type": "application/json"
}


class HttpSinkConfig(BaseSinkConfig):
    url: str
    headers: Dict[str, Any] = None
    base_payload: Dict[str, Any] = None
    # analyzer_output to payload mapping
    payload_mapping: Dict[str, List[str]] = None
    field_conversion: Dict[str, str] = None


class HttpSink(BaseSink):

    def send_data(self, analyzer_responses: List[AnalyzerResponse], config: HttpSinkConfig):

        headers = config.headers or DEFAULT_HEADERS

        payloads = []
        responses = []
        for analyzer_response in analyzer_responses:
            payloads.append(config.convertor.convert(
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
