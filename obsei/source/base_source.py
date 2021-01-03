from abc import abstractmethod
from typing import List

from pydantic.main import BaseModel

from obsei.analyzer.text_analyzer import AnalyzerRequest
from obsei.workflow.store import BaseStore


class BaseSourceConfig(BaseModel):
    TYPE: str = "Base"

    class Config:
        arbitrary_types_allowed = True


class BaseSource(BaseModel):
    store: BaseStore

    @abstractmethod
    def lookup(
        self,
        config: BaseSourceConfig,
        **kwargs
    ) -> List[AnalyzerRequest]:
        pass

    class Config:
        arbitrary_types_allowed = True
