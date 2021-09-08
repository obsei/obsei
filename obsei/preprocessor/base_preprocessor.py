from abc import abstractmethod
from typing import List
from pydantic import BaseSettings

from obsei.payload import TextPayload


class BaseTextProcessorConfig(BaseSettings):
    TYPE: str = "Base"

    class Config:
        arbitrary_types_allowed = True


class BaseTextPreprocessor(BaseSettings):
    TYPE: str = "Base"

    @abstractmethod
    def preprocess_input(
        self, input_list: List[TextPayload], config: BaseTextProcessorConfig, **kwargs
    ) -> List[TextPayload]:
        pass

    class Config:
        arbitrary_types_allowed = True
