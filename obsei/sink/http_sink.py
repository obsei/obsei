from copy import deepcopy
from typing import Any, Dict, List, Optional
from urllib.request import Request, urlopen

from obsei.misc.utils import obj_to_json
from obsei.sink.base_sink import BaseSink, BaseSinkConfig, Convertor
from obsei.payload import TextPayload

DEFAULT_HEADERS = {"Content-type": "application/json"}


class HttpSinkConfig(BaseSinkConfig):
    TYPE: str = "Http"
    url: str
    headers: Optional[Dict[str, Any]] = None
    base_payload: Optional[Dict[str, Any]] = None
    # analyzer_output to payload mapping
    payload_mapping: Optional[Dict[str, List[str]]] = None
    field_conversion: Optional[Dict[str, str]] = None


class HttpSink(BaseSink):
    def __init__(self, convertor: Convertor = Convertor(), **data: Any):
        super().__init__(convertor=convertor, **data)

    def send_data(  # type: ignore[override]
        self, analyzer_responses: List[TextPayload], config: HttpSinkConfig, **kwargs
    ):

        headers = config.headers or DEFAULT_HEADERS

        payloads = []
        responses = []
        for analyzer_response in analyzer_responses:
            payloads.append(
                self.convertor.convert(
                    analyzer_response=analyzer_response,
                    base_payload=dict()
                    if config.base_payload is None
                    else deepcopy(config.base_payload),
                )
            )

        for payload in payloads:
            req = Request(config.url, data=obj_to_json(payload), headers=headers)
            response = urlopen(req)
            responses.append(response)

        return responses
