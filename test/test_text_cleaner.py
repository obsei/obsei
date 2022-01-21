from obsei.payload import TextPayload
from obsei.preprocessor.text_cleaner import TextCleanerConfig
from obsei.preprocessor.text_cleaning_function import DecodeUnicode, RemoveDateTime, RemovePunctuation, \
    RemoveSpecialChars, RemoveStopWords, RemoveWhiteSpaceAndEmptyToken, ReplaceDomainKeywords, ToLowerCase, \
    RegExSubstitute, SpacyLemmatization

TEXT_WITH_WHITE_SPACES = """        If anyone is interested... these are our hosts. I can’t recommend them enough,
Abc & Pbc.         """

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
    request = TextPayload(processed_text=TEXT_WITH_WHITE_SPACES)

    config = TextCleanerConfig(cleaning_functions=[RemoveWhiteSpaceAndEmptyToken()])
    cleaner_responses = text_cleaner.preprocess_input(
        config=config, input_list=[request]
    )
    cleaner_response = cleaner_responses[0]
    assert (
        """If anyone is interested ... these are our hosts . I can ’ t recommend them enough , Abc & Pbc ."""
        == cleaner_response.processed_text
    )


def test_lower_case(text_cleaner):
    request = TextPayload(processed_text=TEXT_WITH_UPPER_CASE)

    config = TextCleanerConfig(cleaning_functions=[ToLowerCase()])
    cleaner_responses = text_cleaner.preprocess_input(
        config=config, input_list=[request]
    )
    cleaner_response = cleaner_responses[0]

    assert "how is this possible ? ? ?" == cleaner_response.processed_text


def test_remove_punctuation(text_cleaner):
    request = TextPayload(processed_text=TEXT_WITH_PUNCTUATION)

    config = TextCleanerConfig(cleaning_functions=[RemovePunctuation()])
    cleaner_responses = text_cleaner.preprocess_input(
        config=config, input_list=[request]
    )
    cleaner_response = cleaner_responses[0]
    assert (
        "I had the worst experience ever with XYZ in Egypt Bad Cars asking to pay in cash"
        == cleaner_response.processed_text
    )


def test_remove_date_time(text_cleaner):
    request = TextPayload(processed_text=TEXT_WITH_DATE_TIME)

    config = TextCleanerConfig(cleaning_functions=[RemoveDateTime()])
    cleaner_responses = text_cleaner.preprocess_input(
        config=config, input_list=[request]
    )
    cleaner_response = cleaner_responses[0]
    assert (
        "Peter drinks likely likes to tea at every" == cleaner_response.processed_text
    )


def test_remove_stop_words(text_cleaner):
    request = TextPayload(processed_text=TEXT_WITH_STOP_WORDS)

    config = TextCleanerConfig(cleaning_functions=[RemoveStopWords(language="english")])
    cleaner_responses = text_cleaner.preprocess_input(
        config=config, input_list=[request]
    )
    cleaner_response = cleaner_responses[0]
    assert "In hello , obsei" == cleaner_response.processed_text


def test_remove_special_characters(text_cleaner):
    request = TextPayload(processed_text=TEXT_WITH_SPECIAL_CHARACTERS)

    config = TextCleanerConfig(cleaning_functions=[RemoveSpecialChars()])

    cleaner_responses = text_cleaner.preprocess_input(
        config=config, input_list=[request]
    )
    cleaner_response = cleaner_responses[0]
    assert (
        "datascience shahrukh lalit developing obsei" == cleaner_response.processed_text
    )


def test_replace_domain_keywords(text_cleaner):
    request = TextPayload(processed_text=TEXT_WITH_DOMAIN_WORDS)

    config = TextCleanerConfig(
        cleaning_functions=[
            ReplaceDomainKeywords(
                domain_keywords=[("ML", "machine learning"), ("DL", "deep learning")]
            )
        ]
    )

    cleaner_responses = text_cleaner.preprocess_input(
        config=config, input_list=[request]
    )
    cleaner_response = cleaner_responses[0]
    assert (
        "deep learning and machine learning are going to change the world and will not overfit"
        == cleaner_response.processed_text
    )


def test_decode_unicode(text_cleaner):
    request = TextPayload(processed_text=TEXT_WITH_UNICODE)

    config = TextCleanerConfig(cleaning_functions=[DecodeUnicode()])

    cleaner_responses = text_cleaner.preprocess_input(
        config=config, input_list=[request]
    )
    cleaner_response = cleaner_responses[0]
    assert "what is this ! ! !" == cleaner_response.processed_text


def test_regex(text_cleaner):
    request = TextPayload(processed_text="Obsei-is-a-lowcode-lib")

    config = TextCleanerConfig(
        cleaning_functions=[
            RegExSubstitute(
                pattern=r'-',
                substitute=" "
            )
        ]
    )

    cleaner_responses = text_cleaner.preprocess_input(
        config=config, input_list=[request]
    )
    cleaner_response = cleaner_responses[0]
    assert (
        "Obsei is a lowcode lib"
        == cleaner_response.processed_text
    )


def test_spacy_lemmatizer(text_cleaner):
    request = TextPayload(processed_text=u'the bats saw the cats with best stripes hanging upside down by their feet')

    config = TextCleanerConfig(
        disable_tokenization=True,
        cleaning_functions=[SpacyLemmatization()]
    )

    cleaner_responses = text_cleaner.preprocess_input(
        config=config, input_list=[request]
    )
    cleaner_response = cleaner_responses[0]
    assert (
        'the bat see the cat with good stripe hang upside down by their foot'
        == cleaner_response.processed_text
    )
