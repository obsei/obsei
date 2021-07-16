from typing import Any, List, Optional
from obsei.payload import TextPayload
from pydantic import BaseModel
from abc import abstractmethod


class BasePostprocessorConfig(BaseModel):
    TYPE: str = "Base"

    class Config:
        multi_label = True


class BasePostprocessor(BaseModel):
    TYPE: str = "Base"

    @abstractmethod
    def postprocess_input(
        self, input_list: List[TextPayload], config: BasePostprocessorConfig, **kwargs
    ) -> List[TextPayload]:
        pass

    class Config:
        arbitrary_types_allowed = True
