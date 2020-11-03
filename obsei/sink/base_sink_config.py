from abc import ABC
from typing import Any, Dict, Optional

from obsei.text_analyzer import AnalyzerResponse


class Convertor(ABC):

    def convert(self, analyzer_response: AnalyzerResponse, base_payload: Optional[Dict[str, Any]] = None) -> dict:

        return {**base_payload, **analyzer_response.to_dict()} \
            if base_payload is not None else analyzer_response.to_dict()


class BaseSinkConfig(ABC):
    def __init__(self, convertor: Convertor):
        self.convertor = convertor
