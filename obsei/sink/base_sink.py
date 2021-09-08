from abc import abstractmethod
from typing import Any, Dict, List, Optional

from pydantic import Field, BaseSettings

from obsei.payload import TextPayload
from obsei.workflow.base_store import BaseStore


class Convertor(BaseSettings):
    def convert(
        self,
        analyzer_response: TextPayload,
        base_payload: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> dict:
        base_payload = base_payload or dict()
        return (
            {**base_payload, **analyzer_response.to_dict()}
            if base_payload is not None
            else analyzer_response.to_dict()
        )

    class Config:
        arbitrary_types_allowed = True


class BaseSinkConfig(BaseSettings):
    TYPE: str = "Base"

    @classmethod
    def from_dict(cls, config: Dict[str, Any]):
        pass

    class Config:
        arbitrary_types_allowed = True


class BaseSink(BaseSettings):
    convertor: Convertor = Field(Convertor())
    store: Optional[BaseStore] = None

    @abstractmethod
    def send_data(
        self, analyzer_responses: List[TextPayload], config: BaseSinkConfig, **kwargs
    ):
        pass

    class Config:
        arbitrary_types_allowed = True
