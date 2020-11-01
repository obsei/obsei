import pytest

from obsei.text_analyzer import TextAnalyzer


@pytest.fixture(scope="session")
def sentiment_classifier():
    return TextAnalyzer(
        classifier_model_name="joeddav/xlm-roberta-large-xnli",
        multi_class_classification=True,
        initialize_sentiment_model=True,
    )
