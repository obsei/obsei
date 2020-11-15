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
    def __init__(
        self,
        url: str,
        convertor: Convertor = Convertor(),
        headers: Dict[str, Any] = None,
        base_payload: Dict[str, Any] = None,
        # analyzer_output to payload mapping
        payload_mapping: Dict[str, List[str]] = None,
        field_conversion: Dict[str, str] = None,
    ):
        self.url = url
        self.headers = headers
        self.base_payload = base_payload
        self.payload_mapping = payload_mapping
        self.field_conversion = field_conversion
        super(HttpSinkConfig, self).__init__(convertor)

    @classmethod
    def from_dict(cls, config: Dict[str, Any]):
        return cls(
            url=config["url"],
            convertor=config["convertor"] if "convertor" in config else Convertor(),
            headers=config["headers"] if "headers" in config else None,
            base_payload=config["base_payload"] if "base_payload" in config else None,
            payload_mapping=config["payload_mapping"] if "payload_mapping" in config else None,
            field_conversion=config["field_conversion"] if "field_conversion" in config else None,
        )


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
