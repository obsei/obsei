import pytest

from obsei.text_analyzer import TextAnalyzer


@pytest.fixture(scope="session")
def text_analyzer_with_model():
    return TextAnalyzer(
        # model_name_or_path="joeddav/xlm-roberta-large-xnli",
        # model_name_or_path="facebook/bart-large-mnli",
        model_name_or_path="joeddav/bart-large-mnli-yahoo-answers",
        multi_class_classification=True,
        initialize_model=True,
    )


@pytest.fixture(scope="session")
def text_analyzer_with_vader():
    return TextAnalyzer()
