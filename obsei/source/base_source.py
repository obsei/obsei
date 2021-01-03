from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from pydantic.main import BaseModel

from obsei.analyzer.text_analyzer import AnalyzerRequest


class BaseSourceConfig(BaseModel):
    TYPE: str = "Base"

    class Config:
        arbitrary_types_allowed = True


class BaseSource(ABC):

    @abstractmethod
    def lookup(
        self,
        config: BaseSourceConfig,
        state: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> List[AnalyzerRequest]:
        pass

    class Config:
        arbitrary_types_allowed = True
