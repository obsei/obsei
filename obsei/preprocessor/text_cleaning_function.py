import logging
import re
import string
from abc import abstractmethod
from typing import Any, List, Optional, Tuple
from unicodedata import normalize

import nltk
from dateutil.parser import parse
from nltk.corpus import stopwords
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class TextCleaningFunction(BaseModel):
    @abstractmethod
    def execute(self, tokens: List[str], **kwargs) -> List[str]:
        pass


class ToLowerCase(TextCleaningFunction):
    def execute(self, tokens: List[str], **kwargs) -> List[str]:
        return [token.lower() for token in tokens]


class RemoveWhiteSpaceAndEmptyToken(TextCleaningFunction):
    def execute(self, tokens: List[str], **kwargs) -> List[str]:
        striped_tokens = [token.strip() for token in tokens]
        return [token for token in striped_tokens if token != ""]


# Removes words that don't add any meaning to the sequence
class RemoveStopWords(TextCleaningFunction):
    stop_words: Optional[List[str]] = None
    language: Optional[str] = "english"

    def __init__(self, **data: Any):
        super().__init__(**data)
        if not self.stop_words:
            try:
                nltk.data.find("stopwords")
            except LookupError:
                nltk.download("stopwords")
            self.stop_words = stopwords.words(self.language)

    def execute(self, tokens: List[str], **kwargs) -> List[str]:
        if not self.stop_words:
            return tokens
        return [token for token in tokens if token not in self.stop_words]


class RemovePunctuation(TextCleaningFunction):
    def execute(self, tokens: List[str], **kwargs) -> List[str]:
        return [
            token.translate(token.maketrans("", "", string.punctuation))  # type: ignore
            for token in tokens
            if len(token.translate(token.maketrans("", "", string.punctuation)))  # type: ignore
        ]


# Transforms tokens to standardized form
class TokenStemming(TextCleaningFunction):
    stemmer: Optional[Any] = None

    def __init__(self, **data: Any):
        super().__init__(**data)
        if not self.stemmer:
            try:
                from nltk.stem import PorterStemmer

                self.stemmer = PorterStemmer()
            except ImportError:
                logger.warning(
                    "NLTK module is not installed hence token stemming will not work"
                )

    def execute(self, tokens: List[str], **kwargs) -> List[str]:
        if not self.stemmer:
            return tokens
        return [self.stemmer.stem(token) for token in tokens]


class RemoveSpecialChars(TextCleaningFunction):
    """
    Removes special characters by eliminating all characters from each token
    and only retains alphabetic, numeric or alphanumeric tokens by stripping
    special characters from them
    """

    def execute(self, tokens: List[str], **kwargs) -> List[str]:
        cleaned_tokens = [re.sub("[^A-Za-z0-9]+", "", token) for token in tokens]
        return [token for token in cleaned_tokens if token != ""]


# Converts unicodes to ASCII characters
class DecodeUnicode(TextCleaningFunction):
    def execute(self, tokens: List[str], **kwargs) -> List[str]:
        return [
            normalize("NFKD", token).encode("ascii", "ignore").decode("utf-8")
            for token in tokens
        ]


class RemoveDateTime(TextCleaningFunction):
    _white_space_cleaner = RemoveWhiteSpaceAndEmptyToken()

    def execute(self, tokens: List[str], **kwargs) -> List[str]:
        text: str = " ".join(tokens)
        try:
            fuzzy_tokens: Tuple[str]
            _, fuzzy_tokens = parse(text, fuzzy_with_tokens=True)  # type: ignore
            tokens = " ".join(fuzzy_tokens).split()
        except ValueError:
            logger.warning("Token contain invalid date time format")
        return self._white_space_cleaner.execute(tokens)


# Replaces domain specific keywords
class ReplaceDomainKeywords(TextCleaningFunction):
    domain_keywords: Optional[List[Tuple[str, str]]] = None

    def execute(self, tokens: List[str], **kwargs) -> List[str]:
        # don't do anything when no domain keywords specified
        if not self.domain_keywords or len(self.domain_keywords) == 0:
            return tokens

        text: str = " ".join(tokens)
        for source_keyword, target_keyword in self.domain_keywords:
            if source_keyword in text or source_keyword.lower() in text:
                text = text.replace(source_keyword, target_keyword)
        tokens = text.split()
        return tokens
