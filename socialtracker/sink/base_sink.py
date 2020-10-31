from abc import ABC, abstractmethod
from typing import List

from socialtracker.sink.base_sink_config import BaseSinkConfig
from socialtracker.text_analyzer import AnalyzerResponse


class BaseSink(ABC):

    @abstractmethod
    def send_data(self, analyzer_response: List[AnalyzerResponse], config: BaseSinkConfig):
        pass
