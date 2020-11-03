from copy import deepcopy
from typing import List

import logging
import requests

from obsei.sink.http_sink_config import HttpSinkConfig
from obsei.sink.base_sink import BaseSink
from obsei.text_analyzer import AnalyzerResponse

logger = logging.getLogger(__name__)

DEFAULT_HEADERS = {
    "Content-type": "application/json"
}


class HttpSink(BaseSink):

    def send_data(self, analyzer_responses: List[AnalyzerResponse], config: HttpSinkConfig):

        headers = config.headers or DEFAULT_HEADERS

        responses = []
        for analyzer_response in analyzer_responses:
            request_payload = config.convertor.convert(
                analyzer_response=analyzer_response,
                base_payload=deepcopy(config.base_payload)
            )

            response = requests.post(
                url=config.url,
                json=request_payload,
                headers=headers,
            )

            logger.info(f"response='{response.__dict__}'")
            responses.append(response)

        return responses
