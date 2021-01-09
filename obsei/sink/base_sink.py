from abc import abstractmethod
from typing import Any, Dict, List, Optional

from pydantic.main import BaseModel

from obsei.analyzer.text_analyzer import AnalyzerResponse
from obsei.workflow.base_store import BaseStore


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


class BaseSink(BaseModel):
    convertor: Convertor
    store: BaseStore

    def __init__(self, **data: Any):
        super().__init__(**data)
        self.convertor = self.convertor or Convertor()

    @abstractmethod
    def send_data(
        self,
        analyzer_responses: List[AnalyzerResponse],
        config: BaseSinkConfig,
        **kwargs
    ):
        pass

    class Config:
        arbitrary_types_allowed = True
