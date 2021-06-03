from pydantic import Field

from obsei.analyzer.base_analyzer import AnalyzerRequest
from obsei.preprocessor.base_preprocessor import (
    BaseTextPreprocessor,
    BaseTextProcessorConfig,
)
from obsei.preprocessor.text_cleaning_function import *
from obsei.preprocessor.text_tokenizer import BaseTextTokenizer, NLTKTextTokenizer


class TextCleanerConfig(BaseTextProcessorConfig):
    cleaning_functions: Optional[List[TextCleaningFunction]] = None
    stop_words_language: Optional[str] = "english"
    stop_words: Optional[List[str]] = None
    domain_keywords: Optional[Tuple[str, str]] = None

    def __init__(self, **data: Any):
        super().__init__(**data)

        if not self.cleaning_functions:
            self.cleaning_functions = [
                ToLowerCase(),
                RemoveWhiteSpaceAndEmptyToken(),
                RemovePunctuation(),
                RemoveSpecialChars(),
                DecodeUnicode(),
                RemoveDateTime(),
                ReplaceDomainKeywords(domain_keywords=self.domain_keywords),
                TokenStemming(),
                RemoveStopWords(
                    language=self.stop_words_language, stop_words=self.stop_words
                ),
                RemoveWhiteSpaceAndEmptyToken(),
            ]


class TextCleaner(BaseTextPreprocessor):
    text_tokenizer: BaseTextTokenizer = Field(NLTKTextTokenizer())

    def preprocess_input(
        self,
        input_list: List[AnalyzerRequest],
        config: TextCleanerConfig,
        **kwargs,
    ) -> List[AnalyzerRequest]:
        if config.cleaning_functions is None:
            return input_list
        for input_data in input_list:
            tokens: List[str] = self.text_tokenizer.tokenize_text(
                input_data.processed_text
            )
            for cleaning_function in config.cleaning_functions:
                tokens = cleaning_function.execute(tokens)
            input_data.processed_text = " ".join(tokens)

        return input_list
