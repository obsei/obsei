import pytest

from obsei.analyzer.classification_analyzer import ZeroShotClassificationAnalyzer
from obsei.analyzer.ner_analyzer import NERAnalyzer
from obsei.analyzer.sentiment_analyzer import VaderSentimentAnalyzer


@pytest.fixture(scope="session")
def zero_shot_analyzer():
    return ZeroShotClassificationAnalyzer(
        model_name_or_path="joeddav/bart-large-mnli-yahoo-answers",
    )


@pytest.fixture(scope="session")
def vader_analyzer():
    return VaderSentimentAnalyzer()


@pytest.fixture(scope="session")
def ner_analyzer():
    return NERAnalyzer(
        model_name_or_path="dbmdz/bert-large-cased-finetuned-conll03-english",
        tokenizer_name="bert-base-cased"
    )
