from abc import abstractmethod
from typing import List, Optional

from pydantic import BaseSettings

from obsei.payload import TextPayload
from obsei.workflow.base_store import BaseStore


class BaseSourceConfig(BaseSettings):
    TYPE: str = "Base"

    class Config:
        arbitrary_types_allowed = True


class BaseSource(BaseSettings):
    store: Optional[BaseStore] = None

    @abstractmethod
    def lookup(self, config: BaseSourceConfig, **kwargs) -> List[TextPayload]:
        pass

    class Config:
        arbitrary_types_allowed = True
