import logging
from abc import abstractmethod
from typing import Any, List, Optional

import nltk
from nltk import word_tokenize
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class BaseTextTokenizer(BaseModel):
    @abstractmethod
    def tokenize_text(self, text: str) -> List[str]:
        pass


class NLTKTextTokenizer(BaseTextTokenizer):
    tokenizer_name: Optional[str] = "punkt"

    def __init__(self, **data: Any):
        super().__init__(**data)
        try:
            nltk.data.find(f"tokenizers/{self.tokenizer_name}")
        except LookupError:
            nltk.download(f"{self.tokenizer_name}")

    def tokenize_text(self, text: str) -> List[str]:
        return word_tokenize(text)
