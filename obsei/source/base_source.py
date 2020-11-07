from abc import ABC, abstractmethod
from typing import List

from obsei.text_analyzer import AnalyzerRequest


class BaseSourceConfig(ABC):
    pass


class BaseSource(ABC):

    @abstractmethod
    def lookup(self, config: BaseSourceConfig) -> List[AnalyzerRequest]:
        pass
