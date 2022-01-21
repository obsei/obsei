import traceback

from obsei.payload import TextPayload
from obsei.preprocessor.base_preprocessor import (
    BaseTextPreprocessor,
    BaseTextProcessorConfig,
)
from obsei.preprocessor.text_cleaning_function import *
from obsei.preprocessor.text_tokenizer import BaseTextTokenizer, NLTKTextTokenizer

logger = logging.getLogger(__name__)


class TextCleanerConfig(BaseTextProcessorConfig):
    cleaning_functions: Optional[List[TextCleaningFunction]] = None
    stop_words_language: Optional[str] = "english"
    stop_words: Optional[List[str]] = None
    domain_keywords: Optional[Tuple[str, str]] = None
    disable_tokenization: bool = False

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
    text_tokenizer: Optional[BaseTextTokenizer] = None

    def __init__(self, **data: Any):
        super().__init__(**data)
        self.text_tokenizer = self.text_tokenizer or NLTKTextTokenizer()

    def preprocess_input(  # type: ignore[override]
        self,
        input_list: List[TextPayload],
        config: TextCleanerConfig,
        **kwargs,
    ) -> List[TextPayload]:
        if config.cleaning_functions is None:
            return input_list
        for input_data in input_list:
            if self.text_tokenizer is None or config.disable_tokenization:
                tokens = [input_data.processed_text]
            else:
                tokens = self.text_tokenizer.tokenize_text(
                    input_data.processed_text
                )
            for cleaning_function in config.cleaning_functions:
                try:
                    tokens = cleaning_function.execute(tokens)
                except Exception as ex:
                    logger.warning(f"Received exception: {ex}")
                    traceback.print_exc()

            input_data.processed_text = " ".join(tokens)

        return input_list
