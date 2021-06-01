from obsei.preprocessor.base_text_cleaner import CleaningFunctions as clean_funcs
from obsei.preprocessor.base_text_cleaner import BaseTextProcessorConfig

from obsei.analyzer.base_analyzer import AnalyzerRequest

import nltk

nltk.download("stopwords")

TEXT_WITH_WHITE_SPACES = """        If anyone is interested... these are our hosts. I can’t recommend them enough, Abc & Pbc.         """

TEXT_WITH_PUNCTUATION = """I had the worst experience ever with XYZ in \"Egypt\". Bad Cars, asking to pay in cash,"""

TEXT_WITH_SPECIAL_CHARACTERS = """#datascience @shahrukh & @lalit developing $obsei"""

TEXT_WITH_DATE_TIME = (
    """Peter drinks likely likes to tea at 16:45 every 15th May 2021"""
)

TEXT_WITH_DOMAIN_WORDS = (
    """DL and ML are going to change the world and will not overfit"""
)

TEXT_WITH_STOP_WORDS = """In off then and hello, obsei"""

TEXT_WITH_UPPER_CASE = """HOW IS THIS POSSIBLE???"""

TEXT_WITH_UNICODE = """what is this \u0021 \u0021 \u0021"""


def test_white_space_cleaner(text_cleaner):
    request = AnalyzerRequest(processed_text=TEXT_WITH_WHITE_SPACES)

    conf = BaseTextProcessorConfig(
        text_cleaning_functions=[
            clean_funcs.remove_white_space,
        ]
    )
    cleaner_responses = text_cleaner.preprocess_input(config=conf, input_list=[request])
    cleaner_response = cleaner_responses[0]
    assert (
        """If anyone is interested ... these are our hosts . I can ’ t recommend them enough , Abc & Pbc ."""
        == cleaner_response.processed_text
    )


def test_lower_case(text_cleaner):
    request = AnalyzerRequest(processed_text=TEXT_WITH_UPPER_CASE)

    conf = BaseTextProcessorConfig(
        text_cleaning_functions=[
            clean_funcs.to_lower_case,
        ]
    )
    cleaner_responses = text_cleaner.preprocess_input(config=conf, input_list=[request])
    cleaner_response = cleaner_responses[0]

    assert "how is this possible ? ? ?" == cleaner_response.processed_text


def test_remove_punctuation(text_cleaner):
    request = AnalyzerRequest(processed_text=TEXT_WITH_PUNCTUATION)

    conf = BaseTextProcessorConfig(
        text_cleaning_functions=[
            clean_funcs.remove_punctuation,
        ]
    )
    cleaner_responses = text_cleaner.preprocess_input(config=conf, input_list=[request])
    cleaner_response = cleaner_responses[0]
    assert (
        "I had the worst experience ever with XYZ in Egypt Bad Cars asking to pay in cash"
        == cleaner_response.processed_text
    )


def test_remove_date_time(text_cleaner):
    request = AnalyzerRequest(processed_text=TEXT_WITH_DATE_TIME)

    conf = BaseTextProcessorConfig(
        text_cleaning_functions=[
            clean_funcs.remove_date_time,
        ]
    )
    cleaner_responses = text_cleaner.preprocess_input(config=conf, input_list=[request])
    cleaner_response = cleaner_responses[0]
    assert "Peter drinks likely likes to tea at" == cleaner_response.processed_text


def test_remove_stop_words(text_cleaner):
    request = AnalyzerRequest(processed_text=TEXT_WITH_STOP_WORDS)

    conf = BaseTextProcessorConfig(
        text_cleaning_functions=[
            clean_funcs.remove_stop_words,
        ]
    )
    cleaner_responses = text_cleaner.preprocess_input(config=conf, input_list=[request])
    cleaner_response = cleaner_responses[0]
    assert "In hello , obsei" == cleaner_response.processed_text


def test_remove_special_characters(text_cleaner):
    request = AnalyzerRequest(processed_text=TEXT_WITH_SPECIAL_CHARACTERS)

    conf = BaseTextProcessorConfig(
        text_cleaning_functions=[
            clean_funcs.remove_special_characters,
        ]
    )

    cleaner_responses = text_cleaner.preprocess_input(config=conf, input_list=[request])
    cleaner_response = cleaner_responses[0]
    assert (
        "datascience shahrukh lalit developing obsei" == cleaner_response.processed_text
    )


def test_replace_domain_keywords(text_cleaner):
    request = AnalyzerRequest(processed_text=TEXT_WITH_DOMAIN_WORDS)

    conf = BaseTextProcessorConfig(
        text_cleaning_functions=[
            clean_funcs.replace_domain_keywords,
        ]
    )

    cleaner_responses = text_cleaner.preprocess_input(config=conf, input_list=[request])
    cleaner_response = cleaner_responses[0]
    assert (
        "deep learning and machine learning are going to change the world and will not overfit"
        == cleaner_response.processed_text
    )


def test_decode_unicode(text_cleaner):
    request = AnalyzerRequest(processed_text=TEXT_WITH_UNICODE)

    conf = BaseTextProcessorConfig(
        text_cleaning_functions=[
            clean_funcs.decode_unicode,
        ]
    )

    cleaner_responses = text_cleaner.preprocess_input(config=conf, input_list=[request])
    cleaner_response = cleaner_responses[0]
    assert "what is this ! ! !" == cleaner_response.processed_text
