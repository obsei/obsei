from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from pydantic.main import BaseModel

from obsei.analyzer.text_analyzer import AnalyzerResponse


class Convertor(BaseModel):

    def convert(
        self,
        analyzer_response: AnalyzerResponse,
        base_payload: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> dict:

        return {**base_payload, **analyzer_response.to_dict()} \
            if base_payload is not None else analyzer_response.to_dict()

    class Config:
        arbitrary_types_allowed = True


class BaseSinkConfig(BaseModel):
    TYPE: str = "Base"

    @classmethod
    def from_dict(cls, config: Dict[str, Any]):
        pass

    class Config:
        arbitrary_types_allowed = True


class BaseSink(ABC):
    def __init__(self, convertor: Convertor = Convertor()):
        self.convertor = convertor

    @abstractmethod
    def send_data(self, analyzer_responses: List[AnalyzerResponse], config: BaseSinkConfig):
        pass
