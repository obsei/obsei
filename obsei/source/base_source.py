from abc import ABC, abstractmethod
from typing import Any, Dict, List

from obsei.text_analyzer import AnalyzerRequest


class BaseSourceConfig(ABC):
    @classmethod
    def from_dict(cls, config: Dict[str, Any]):
        pass


class BaseSource(ABC):

    @abstractmethod
    def lookup(self, config: BaseSourceConfig) -> List[AnalyzerRequest]:
        pass
