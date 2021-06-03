from abc import abstractmethod
from typing import Any, List
from pydantic import BaseModel

from obsei.analyzer.base_analyzer import AnalyzerRequest


class BaseTextProcessorConfig(BaseModel):
    TYPE: str = "Base"

    class Config:
        arbitrary_types_allowed = True


class BaseTextPreprocessor(BaseModel):
    TYPE: str = "Base"

    @abstractmethod
    def preprocess_input(
        self,
        input_list: List[AnalyzerRequest],
        config: BaseTextProcessorConfig,
        **kwargs
    ) -> List[AnalyzerRequest]:
        pass

    class Config:
        arbitrary_types_allowed = True
