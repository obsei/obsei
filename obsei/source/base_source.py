from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from pydantic.main import BaseModel

from obsei.analyzer.text_analyzer import AnalyzerRequest
from obsei.workflow.store import WorkflowStore


class BaseSourceConfig(BaseModel):
    TYPE: str = "Base"

    class Config:
        arbitrary_types_allowed = True


class BaseSource(ABC):
    store: WorkflowStore = WorkflowStore()

    @abstractmethod
    def lookup(
        self,
        config: BaseSourceConfig,
        **kwargs
    ) -> List[AnalyzerRequest]:
        pass

    class Config:
        arbitrary_types_allowed = True
