from abc import abstractmethod
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, PrivateAttr


class TextCleanerRequest(BaseModel):
    text: str


class TextCleanerResponse(BaseModel):
    text: str
    processed_text: str


class BaseTextCleanerConfig(BaseModel):
    TYPE: str = "Base"

    class Config:
        arbitrary_types_allowed = True


class BaseTextCleaner(BaseModel):
    TYPE: str = "Base"

    def __init__(self, **data: Any):
        super().__init__(**data)
    
    @abstractmethod
    def clean_input(
        self,
        input_list: List[TextCleanerRequest],
        config: BaseTextCleanerConfig,
        **kwargs
    ) -> List[TextCleanerResponse]:
        pass

    class Config:
        arbitrary_types_allowed = True
