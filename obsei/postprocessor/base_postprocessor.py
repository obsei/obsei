from typing import List
from obsei.payload import TextPayload
from pydantic import BaseSettings
from abc import abstractmethod


class BasePostprocessorConfig(BaseSettings):
    TYPE: str = "Base"

    class Config:
        multi_label = True


class BasePostprocessor(BaseSettings):
    TYPE: str = "Base"

    @abstractmethod
    def postprocess_input(
        self, input_list: List[TextPayload], config: BasePostprocessorConfig, **kwargs
    ) -> List[TextPayload]:
        pass

    class Config:
        arbitrary_types_allowed = True
