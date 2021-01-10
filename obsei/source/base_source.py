from abc import abstractmethod
from typing import List, Optional

from pydantic.main import BaseModel

from obsei.analyzer.text_analyzer import AnalyzerRequest
from obsei.workflow.base_store import BaseStore


class BaseSourceConfig(BaseModel):
    TYPE: str = "Base"

    class Config:
        arbitrary_types_allowed = True


class BaseSource(BaseModel):
    store: Optional[BaseStore] = None

    @abstractmethod
    def lookup(
        self,
        config: BaseSourceConfig,
        **kwargs
    ) -> List[AnalyzerRequest]:
        pass

    class Config:
        arbitrary_types_allowed = True
