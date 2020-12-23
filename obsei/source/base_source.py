from abc import ABC, abstractmethod
from typing import List

from pydantic.main import BaseModel

from obsei.analyzer.text_analyzer import AnalyzerRequest


class BaseSourceConfig(BaseModel):
    TYPE: str = "Base"

    class Config:
        arbitrary_types_allowed = True


class BaseSource(ABC):

    @abstractmethod
    def lookup(self, config: BaseSourceConfig) -> List[AnalyzerRequest]:
        pass

    class Config:
        arbitrary_types_allowed = True
