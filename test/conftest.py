import pytest

from obsei.text_analyzer import TextAnalyzer


@pytest.fixture(scope="session")
def text_analyzer_with_model():
    return TextAnalyzer(
        # classifier_model_name="joeddav/xlm-roberta-large-xnli",
        # classifier_model_name="facebook/bart-large-mnli",
        classifier_model_name="joeddav/bart-large-mnli-yahoo-answers",
        multi_class_classification=True,
        initialize_model=True,
    )


@pytest.fixture(scope="session")
def text_analyzer_with_vader():
    return TextAnalyzer()
