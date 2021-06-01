import logging
from typing import Any, Dict, List, Optional
import string
import re
from unicodedata import normalize as unicode_decode
from dateutil.parser import parse

from nltk.stem import PorterStemmer
import nltk
from nltk.corpus import stopwords
from nltk.tokenize import word_tokenize

from pydantic import PrivateAttr

from obsei.analyzer.base_analyzer import AnalyzerRequest
from obsei.preprocessor.base_text_cleaner import (
    BaseTextPreprocessor,
    BaseTextProcessorConfig,
)

logger = logging.getLogger(__name__)


class TextCleaner(BaseTextPreprocessor):
    """
    Cleanses the Text sequences by removing stop words, dates, white spaces etc.
    """

    stemmer: Optional[Any] = PorterStemmer()
    language: Optional[str] = "english"
    tokenizer_name: Optional[str] = "punkt"
    domain_keywords: Optional[List] = []
    stop_words: Optional[List[str]]

    def __init__(self, **data: Any):
        super().__init__(**data)
        self.stop_words = stopwords.words(self.language)

    def preprocess_input(
        self,
        input_list: List[AnalyzerRequest],
        config: BaseTextProcessorConfig,
        **kwargs,
    ) -> List[AnalyzerRequest]:
        """
        Executes the text preprocessing pipeline based on the config state

        Args:
            input_list (List[AnalyzerRequest]): List of text sequences and other inputs
            config (BaseTextProcessorConfig): Configuration of text cleaning pipeline
            which includes choice of stemmer, stop words etc.

        Returns:
            List[AnalyzerRequest]: Cleansed and Processed list of text sequences
        """
        try:
            nltk.data.find(f"tokenizers/{self.tokenizer_name}")
        except LookupError:
            nltk.download(f"{self.tokenizer_name}")

        for index, input in enumerate(input_list):
            tokens: List[str] = self.tokenize_text(input.processed_text)
            for text_cleaning_function in config.text_cleaning_functions:
                tokens = eval(f"self.{text_cleaning_function}({tokens})")
            input_list[index].processed_text = " ".join(tokens)

        return input_list

    def tokenize_text(self, text: str) -> List[str]:
        """
        Transforms text string to words using NLTK's tokenizer

        Args:
            text (str): Text sequence

        Returns:
            List[str]: List of word tokens
        """
        return word_tokenize(text)

    def to_lower_case(self, tokens: List[str]) -> List[str]:
        """
        Transforms string tokens to lower case

        Args:
            tokens (List[str]): [description]

        Returns:
            List[str]: [description]
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
        text: str = " ".join(tokens).strip()
        return text.split()

    def remove_special_characters(self, tokens: List[str]) -> List[str]:
        """
        Removes special characters by eliminating all characters from each token
        and only retains alphabetic, numeric or alphanumeric tokens by stripping
        special characters from them

        Args:
            tokens (List[str]): List of word tokens

        Returns:
            List[str]: List of word tokens with each token with speical characters
            removed
        """
        return [
            re.sub("[^A-Za-z0-9]+", "", token)
            for token in tokens
            if len(re.sub("[^A-Za-z0-9]+", "", token))
        ]

    def decode_unicode(self, tokens: List[str]) -> List[str]:
        """
        Converts unicodes to ASCII characters

        Args:
            tokens (List[str]): List of word tokens

        Returns:
            List[str]: List of word tokens with unicodes converted to ASCII
        """
        return [
            unicode_decode("NFKD", token).encode("ascii", "ignore").decode("utf-8")
            for token in tokens
        ]

    def remove_date_time(self, tokens: List[str]) -> List[str]:
        """
        Removes date or time mentions from text

        Args:
            tokens (List[str]): List of word tokens

        Returns:
            List[str]: List of word tokens with dates/times removes
        """
        text: str = " ".join(tokens)
        try:
            tokens = parse(text, fuzzy_with_tokens=True)[1][0].split()
        except:
            pass
        return tokens

    def replace_domain_keywords(self, tokens: List[str]) -> List[str]:
        """
        Replaces domain specific keywords

        Args:
            tokens (List[str]): List of word tokens

        Returns:
            List[str]: List of word tokens substituted with mapped domain words
        """
        # don't do anything when no domain keywords specified
        if not len(self.domain_keywords):
            return tokens

        text: str = " ".join(tokens)
        for source_keyword, target_keyword in self.domain_keywords:
            if source_keyword in text or source_keyword.lower() in text:
                text = text.replace(source_keyword, target_keyword)
        tokens: List[str] = text.split()
        return tokens
