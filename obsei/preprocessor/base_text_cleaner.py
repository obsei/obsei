from abc import abstractmethod
from typing import Any, Dict, List, Optional
from enum import Enum
from pydantic import BaseModel, PrivateAttr

from obsei.analyzer.base_analyzer import AnalyzerRequest


class CleaningFunctions(str, Enum):
    to_lower_case: str = "to_lower_case"
    remove_white_space: str = "remove_white_space"
    remove_punctuation: str = "remove_punctuation"
    remove_special_characters: str = "remove_special_characters"
    decode_unicode: str = "decode_unicode"
    remove_date_time: str = "remove_date_time"
    replace_domain_keywords: str = "replace_domain_keywords"
    stem_text: str = "stem_text"
    remove_stop_words: str = "remove_stop_words"


class BaseTextProcessorConfig(BaseModel):
    TYPE: str = "Base"
    text_cleaning_functions: Optional[List[CleaningFunctions]]
    domain_keywords: Optional[List[Dict]] = []
    tokenizer_name: Optional[str] = "punkt"

    class Config:
        arbitrary_types_allowed = True
        use_enum_values = True


class BaseTextPreprocessor(BaseModel):
    TYPE: str = "Base"

    def __init__(self, **data: Any):
        super().__init__(**data)

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
