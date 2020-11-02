from obsei.source.base_source import SourceResponse

GOOD_TEXT = '''If anyone is interested... these are our hosts. I can’t recommend them enough, Abc & Pbc.

The unit is just lovely, you go to sleep & wake up to this incredible place, and you have use of a Weber grill and a ridiculously indulgent hot-tub under the stars'''

BAD_TEXT = '''I had the worst experience ever with XYZ in Egypt. Bad Cars, asking to pay in cash,  do not have enough fuel,  do not open AC,  wait far away from my location until the trip is cancelled,  call and ask about the destination then cancel, and more. Worst service.'''

MIXED_TEXT = '''I am mixed'''

TEXTS = [GOOD_TEXT, BAD_TEXT, MIXED_TEXT]


def test_text_analyzer_with_model(text_analyzer_with_model):
    labels = ["facility", "food", "comfortable"]

    source_responses = [SourceResponse(text) for text in TEXTS]
    analyzer_responses = text_analyzer_with_model.analyze_input(
        source_response_list=source_responses,
        labels=labels,
        use_sentiment_model=True
    )

    assert len(analyzer_responses) == len(TEXTS)

    for analyzer_response in analyzer_responses:
        assert len(analyzer_response.classification) == len(labels)
        assert analyzer_response.sentiment_type in ["POSITIVE", "NEGATIVE"]
        assert -1.0 <= analyzer_response.sentiment_value <= 1.0


def test_text_analyzer_with_vader(text_analyzer_with_vader):
    source_responses = [SourceResponse(text) for text in TEXTS]
    analyzer_responses = text_analyzer_with_vader.analyze_input(
        source_response_list=source_responses
    )

    assert len(analyzer_responses) == len(TEXTS)

    for analyzer_response in analyzer_responses:
        if analyzer_response.processed_text == GOOD_TEXT:
            assert analyzer_response.sentiment_type == "POSITIVE"
            assert analyzer_response.sentiment_value > 0.0
        elif analyzer_response.processed_text == BAD_TEXT:
            assert analyzer_response.sentiment_type == "NEGATIVE"
            assert analyzer_response.sentiment_value < 0.0
        else:
            assert analyzer_response.sentiment_type in ["POSITIVE", "NEGATIVE"]
            assert -0.5 < analyzer_response.sentiment_value < 0.75
