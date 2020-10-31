from copy import deepcopy
from typing import List

import logging
import requests

from socialtracker.sink.http_sink_config import HttpSinkConfig
from socialtracker.sink.base_sink import BaseSink
from socialtracker.text_analyzer import AnalyzerResponse

logger = logging.getLogger(__name__)

DEFAULT_HEADERS = {
    "Content-type": "application/json"
}

DEFAULT_PAYLOAD_MAPPING = {
    "text": ["text"],
    "sentiment_value": ["sentiment_value"],
    "sentiment_type": ["sentiment_type"],
    "classification_map": ["classification_map"],
    "meta_information": ["meta_information"],
}


class HttpSink(BaseSink):

    def send_data(self, analyzer_responses: List[AnalyzerResponse], config: HttpSinkConfig):

        headers = config.headers or DEFAULT_HEADERS
        payload_mapping = config.payload_mapping or DEFAULT_PAYLOAD_MAPPING
        base_payload = config.base_payload or {}

        responses = []
        for analyzer_response in analyzer_responses:

            analyzer_response_dict = analyzer_response.to_dict()
            request_payload = deepcopy(base_payload)

            for analyzer_response_key, request_payload_keys in payload_mapping.items():
                for idx, request_payload_key in enumerate(request_payload_keys):
                    if idx == len(request_payload_keys) - 1:
                        request_payload[request_payload_key] = analyzer_response_dict[analyzer_response_key]
                    else:
                        request_payload[request_payload_key] = {}

            response = requests.post(
                url=config.url,
                data=request_payload,
                headers=headers,
            )

            logger.info(f"response='{response}'")
            responses.append(response)
