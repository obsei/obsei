from abc import abstractmethod
from typing import Any, Dict, List, Optional, Type, TypeVar

from pydantic import Field
from pydantic_settings import BaseSettings

from obsei.payload import TextPayload
from obsei.workflow.base_store import BaseStore


class Convertor(BaseSettings):
    def convert(
            self,
            analyzer_response: TextPayload,
            base_payload: Optional[Dict[str, Any]] = None,
            **kwargs: Any
    ) -> Dict[str, Any]:
        base_payload = base_payload or dict()
        return (
            {**base_payload, **analyzer_response.to_dict()}
            if base_payload is not None
            else analyzer_response.to_dict()
        )

    class Config:
        arbitrary_types_allowed = True


T = TypeVar('T', bound='BaseSinkConfig')


class BaseSinkConfig(BaseSettings):
    TYPE: str = "Base"

    @classmethod
    def from_dict(cls: Type[T], config: Dict[str, Any]) -> T:  # type: ignore[empty-body]
        pass

    class Config:
        arbitrary_types_allowed = True


class BaseSink(BaseSettings):
    convertor: Convertor = Field(Convertor())
    store: Optional[BaseStore] = None

    @abstractmethod
    def send_data(
            self, analyzer_responses: List[TextPayload], config: BaseSinkConfig, **kwargs: Any
    ) -> Any:
        pass

    class Config:
        arbitrary_types_allowed = True
