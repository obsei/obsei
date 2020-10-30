import pytest

GOOD_TEXT = '''If anyone is interested... these are our hosts. I can’t recommend them enough, Abc & Pbc.

The unit is just lovely, you go to sleep & wake up to this incredible place, and you have use of a Weber grill and a ridiculously indulgent hot-tub under the stars'''

BAD_TEXT = '''I had the worst experience ever with XYZ in Egypt. Bad Cars, asking to pay in cash,  do not have enough fuel,  do not open AC,  wait far away from my location until the trip is cancelled,  call and ask about the destination then cancel, and more. Worst service.'''

MIXED_TEXT = '''I am mixed'''


@pytest.mark.parametrize("use_sentiment_model", [True, False])
def test_good_sentiment(sentiment_classifier, use_sentiment_model):
    labels = ["facility", "food", "comfortable"]
    score_dict = sentiment_classifier.classify_text(GOOD_TEXT, labels)

    for label, score in score_dict.items():
        print(label, "=", score)

    sentiment_score = sentiment_classifier.get_sentiment_score(GOOD_TEXT, use_sentiment_model)

    print("\nsentiment_score=", sentiment_score)

    assert len(labels) == len(score_dict)
    assert sentiment_score > 0


@pytest.mark.parametrize("use_sentiment_model", [True, False])
def test_bad_sentiment(sentiment_classifier, use_sentiment_model):
    labels = ["experience", "service", "comfortable"]
    score_dict = sentiment_classifier.classify_text(BAD_TEXT, labels)

    for label, score in score_dict.items():
        print(label, "=", score)

    sentiment_score = sentiment_classifier.get_sentiment_score(BAD_TEXT, use_sentiment_model)

    print("\nsentiment_score=", sentiment_score)

    assert len(labels) == len(score_dict)
    assert sentiment_score < 0


@pytest.mark.parametrize("use_sentiment_model", [True, False])
def test_mixed_sentiment(sentiment_classifier, use_sentiment_model):
    labels = ["feeling", "data", "trust"]
    score_dict = sentiment_classifier.classify_text(MIXED_TEXT, labels)

    for label, score in score_dict.items():
        print(label, "=", score)

    sentiment_score = sentiment_classifier.get_sentiment_score(MIXED_TEXT, use_sentiment_model)

    print("\nsentiment_score=", sentiment_score)

    assert len(labels) == len(score_dict)
    if use_sentiment_model:
        # Sentiment model is highly polarized
        assert sentiment_score < 0
    else:
        assert 0.75 > sentiment_score > -0.25
