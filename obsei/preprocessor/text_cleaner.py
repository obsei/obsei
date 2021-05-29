import logging
from typing import Any, Dict, List, Optional
import string
import re
from unicodedata import normalize as unicode_decode
from dateutil.parser import parse

import nltk
from nltk.corpus import stopwords
from nltk.stem import PorterStemmer
from nltk.tokenize import word_tokenize

from pydantic import PrivateAttr

from obsei.analyzer.base_analyzer import AnalyzerRequest
from obsei.preprocessor.base_text_cleaner import (
    BaseTextPreprocessor,
    BaseTextProcessorConfig,
)

logger = logging.getLogger(__name__)
try:
    nltk.data.find("tokenizers/punkt")
except LookupError:
    nltk.download("punkt")


class TextCleaner(BaseTextPreprocessor):
    text_cleaning_functions: List = []

    def __init__(self, **data: Any):
        super().__init__(**data)
        self.stemmer = data.get("stemmer", PorterStemmer())
        self.domain_keywords = data.get("domain_keywords", [])
        TextCleaner.text_cleaning_functions = [
            {
                "function": self.to_lower_case,
                "name": "to_lower_case",
                "is_enabled": True,
            },
            {
                "function": self.remove_white_space,
                "name": "remove_white_space",
                "is_enabled": True,
            },
            {
                "function": self.remove_punctuation,
                "name": "remove_punctuation",
                "is_enabled": True,
            },
            {
                "function": self.remove_special_characters,
                "name": "remove_special_characters",
                "is_enabled": True,
            },
            {
                "function": self.decode_unicode,
                "name": "decode_unicode",
                "is_enabled": True,
            },
            {
                "function": self.remove_date_time,
                "name": "remove_date_time",
                "is_enabled": True,
            },
            {
                "function": self.replace_domain_keywords,
                "name": "replace_domain_keywords",
                "is_enabled": True,
            },
            {"function": self.stem_text, "name": "stem_text", "is_enabled": True},
            {
                "function": self.remove_stop_words,
                "name": "remove_stop_words",
                "is_enabled": True,
            },
        ]

    def clean_input(
        self,
        input_list: List[AnalyzerRequest],
        config: BaseTextProcessorConfig,
        **kwargs
    ) -> List[AnalyzerRequest]:
        self.stop_words: List = stopwords.words(config.language)
        text_cleaning_functions_config: List[Dict] = (
            config.text_cleaning_functions or TextCleaner.text_cleaning_functions
        )
        for index, input in enumerate(input_list):
            tokens: List[str] = self.tokenize_text(input.processed_text)
            for text_cleaning_function_config in text_cleaning_functions_config:
                if text_cleaning_function_config["is_enabled"]:
                    tokens = text_cleaning_function_config["function"](tokens)
            input_list[index].processed_text = " ".join(tokens)

        return input_list

    def tokenize_text(self, text: str) -> List[str]:
        """
        Transforms text string to words using NLTK's tokenizer
        """
        return word_tokenize(text)

    def to_lower_case(self, tokens: List[str]) -> List[str]:
        """
        Transforms string tokens to lower case
        """
        return [token.lower() for token in tokens]

    def remove_stop_words(self, tokens: List[str]) -> List[str]:
        """
        Removes words that don't add any meaning to the sequence
        """
        return [token for token in tokens if token not in self.stop_words]

    def remove_punctuation(self, tokens: List[str]) -> List[str]:
        """
        Removes punctuations from each token
        """
        return [
            token.translate(token.maketrans("", "", string.punctuation))
            for token in tokens
            if len(token.translate(token.maketrans("", "", string.punctuation)))
        ]

    def stem_text(self, tokens: List[str]) -> List[str]:
        """
        Transforms tokens to standardized form
        """
        return [self.stemmer.stem(token) for token in tokens]

    def remove_white_space(self, tokens: List[str]) -> List[str]:
        """
        Transforms string tokens to lower case
        """
        return [token.strip() for token in tokens if len(token.strip())]

    def remove_special_characters(self, tokens: List[str]) -> List[str]:
        """
        Removes special characters by eliminating all characters from each token
        and only retains alphabetic, numeric or alphanumeric tokens by stripping
        special characters from them
        """
        return [
            re.sub("[^A-Za-z0-9]+", "", token)
            for token in tokens
            if len(re.sub("[^A-Za-z0-9]+", "", token))
        ]

    def decode_unicode(self, tokens: List[str]) -> List[str]:
        """
        Converts unicodes to ASCII characters
        """
        return [
            unicode_decode("NFKD", token).encode("ascii", "ignore").decode("utf-8")
            for token in tokens
        ]

    def remove_date_time(self, tokens: List[str]) -> List[str]:
        """
        Removes date or time mentions from text
        """
        text: str = " ".join(tokens)
        return parse(text, fuzzy_with_tokens=True)[1][0].split()

    def replace_domain_keywords(self, tokens: List[str]) -> List[str]:
        """
        Replaces domain specific keywords
        """
        # don't do anything when no domain keywords specified
        if not len(self.domain_keywords):
            return tokens

        text: str = " ".join(tokens)
        for domain_keyword in self.domain_keywords:
            source_keyword, target_keyword = domain_keyword
            if source_keyword in text:
                text = text.replace(source_keyword, target_keyword)
        tokens: List[str] = text.split()
        return tokens
