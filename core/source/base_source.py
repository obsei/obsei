from abc import abstractmethod
from typing import List, Optional, Any

from pydantic_settings import BaseSettings

from core.payload import TextPayload
from core.workflow.base_store import BaseStore


class BaseSourceConfig(BaseSettings):
    TYPE: str = "Base"

    class Config:
        arbitrary_types_allowed = True


class BaseSource(BaseSettings):
    store: Optional[BaseStore] = None

    @abstractmethod
    def lookup(self, config: BaseSourceConfig, **kwargs: Any) -> List[TextPayload]:
        pass

    class Config:
        arbitrary_types_allowed = True
