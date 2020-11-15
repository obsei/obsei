from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from obsei.text_analyzer import AnalyzerResponse


class Convertor(ABC):

    def convert(self, analyzer_response: AnalyzerResponse, base_payload: Optional[Dict[str, Any]] = None, **kwargs) -> dict:

        return {**base_payload, **analyzer_response.to_dict()} \
            if base_payload is not None else analyzer_response.to_dict()


class BaseSinkConfig(ABC):
    def __init__(self, convertor: Convertor):
        self.convertor = convertor

    @classmethod
    def from_dict(cls, config: Dict[str, Any]):
        pass


class BaseSink(ABC):

    @abstractmethod
    def send_data(self, analyzer_responses: List[AnalyzerResponse], config: BaseSinkConfig):
        pass
