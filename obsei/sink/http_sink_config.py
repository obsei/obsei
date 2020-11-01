from typing import Any, Dict, List

from obsei.sink.base_sink_config import BaseSinkConfig


class HttpSinkConfig(BaseSinkConfig):
    def __init__(
        self,
        url,
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
