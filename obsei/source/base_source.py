from abc import ABC, abstractmethod
from typing import List, Literal

from pydantic.main import BaseModel

from obsei.text_analyzer import AnalyzerRequest


class BaseSourceConfig(BaseModel):
    TYPE: Literal["Base"] = "Base"

    class Config:
        arbitrary_types_allowed = True


class BaseSource(ABC):

    @abstractmethod
    def lookup(self, config: BaseSourceConfig) -> List[AnalyzerRequest]:
        pass

    class Config:
        arbitrary_types_allowed = True
