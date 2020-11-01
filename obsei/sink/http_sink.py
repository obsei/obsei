from copy import deepcopy
from typing import Dict, List

import logging
import requests

from obsei.sink.http_sink_config import HttpSinkConfig
from obsei.sink.base_sink import BaseSink
from obsei.text_analyzer import AnalyzerResponse

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
        base_payload = config.base_payload or {}
        payload_mapping = config.payload_mapping or DEFAULT_PAYLOAD_MAPPING
        reverse_payload_mapping: Dict[str, List[str]] = {}

        for analyzer_response_key, request_payload_keys in payload_mapping.items():
            payload_last_key = request_payload_keys[-1]
            if payload_last_key not in reverse_payload_mapping:
                reverse_payload_mapping[payload_last_key] = []
            reverse_payload_mapping[payload_last_key].append(analyzer_response_key)

        responses = []
        for analyzer_response in analyzer_responses:

            analyzer_response_dict = analyzer_response.to_dict()
            request_payload = deepcopy(base_payload)

            # TODO: Clean this
            for analyzer_response_key, request_payload_keys in payload_mapping.items():
                current_payload_ref = request_payload
                for idx, request_payload_key in enumerate(request_payload_keys):
                    if request_payload_key not in current_payload_ref:
                        current_payload_ref[request_payload_key] = {}

                    if idx == len(request_payload_keys) - 1:
                        if len(reverse_payload_mapping[request_payload_key]) == 0:
                            current_payload_ref[request_payload_key] = analyzer_response_dict[analyzer_response_key]
                        else:
                            current_payload_ref[request_payload_key][analyzer_response_key] = analyzer_response_dict[analyzer_response_key]
                    else:
                        current_payload_ref = current_payload_ref[request_payload_key]

            # TODO: Clean this
            if "enquiryMessage" in request_payload:
                if isinstance(request_payload["enquiryMessage"], Dict):
                    value = request_payload["enquiryMessage"]
                    request_payload["enquiryMessage"] = ""
                    for k, v in value.items():
                        if isinstance(v, List):
                            request_payload["enquiryMessage"] += str(k) + ":" + ",".join(v).replace("\n", "") + "\n"
                        else:
                            request_payload["enquiryMessage"] += str(k) + ":" + str(v).replace("\n", "") + "\n"

            response = requests.post(
                url=config.url,
                json=request_payload,
                headers=headers,
            )

            logger.info(f"response='{response.__dict__}'")
            responses.append(response)

        return responses