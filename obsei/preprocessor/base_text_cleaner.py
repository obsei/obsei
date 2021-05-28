from abc import abstractmethod
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, PrivateAttr


from obsei.analyzer.base_analyzer import AnalyzerRequest

class BaseTextCleanerConfig(BaseModel):
    TYPE: str = "Base"
    text_cleaning_functions: Optional[List[Dict]]
    class Config:
        arbitrary_types_allowed = True


class BaseTextCleaner(BaseModel):
    TYPE: str = "Base"
    stop_words: Optional[List[str]] = []
    domain_keywords: Optional[List[Dict]] = []
    stemmer: Any
    def __init__(self, **data: Any):
        super().__init__(**data)
    
    @abstractmethod
    def clean_input(
        self,
        input_list: List[AnalyzerRequest],
        config: BaseTextCleanerConfig,
        **kwargs
    ) -> List[AnalyzerRequest]:
        pass

    class Config:
        arbitrary_types_allowed = True
