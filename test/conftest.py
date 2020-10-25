import pytest

from socialtracker.classification import SentimentClassifier


@pytest.fixture(scope="session")
def sentiment_classifier():
    return SentimentClassifier("joeddav/xlm-roberta-large-xnli")