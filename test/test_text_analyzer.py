from obsei.analyzer.text_analyzer import AnalyzerConfig, AnalyzerRequest

GOOD_TEXT = '''If anyone is interested... these are our hosts. I can’t recommend them enough, Abc & Pbc.

The unit is just lovely, you go to sleep & wake up to this incredible place, and you have use of a Weber grill and a ridiculously indulgent hot-tub under the stars'''

BAD_TEXT = '''I had the worst experience ever with XYZ in Egypt. Bad Cars, asking to pay in cash,  do not have enough fuel,  do not open AC,  wait far away from my location until the trip is cancelled,  call and ask about the destination then cancel, and more. Worst service.'''

MIXED_TEXT = '''I am mixed'''

TEXTS = [GOOD_TEXT, BAD_TEXT, MIXED_TEXT]


def test_text_analyzer_with_model(text_analyzer_with_model):
    labels = ["facility", "food", "comfortable", "positive", "negative"]

    source_responses = [AnalyzerRequest(text, "sample") for text in TEXTS]
    analyzer_responses = text_analyzer_with_model.analyze_input(
        source_response_list=source_responses,
        analyzer_config=AnalyzerConfig(
            labels=labels,
            use_sentiment_model=True
        )
    )

    assert len(analyzer_responses) == len(TEXTS)

    for analyzer_response in analyzer_responses:
        assert len(analyzer_response.classification) == len(labels)
        assert "positive" in analyzer_response.classification
        assert "negative" in analyzer_response.classification


def test_text_analyzer_with_vader(text_analyzer_with_vader):
    source_responses = [AnalyzerRequest(text, "sample") for text in TEXTS]
    analyzer_responses = text_analyzer_with_vader.analyze_input(
        source_response_list=source_responses,
        analyzer_config=AnalyzerConfig(
            use_sentiment_model=False
        )
    )

    assert len(analyzer_responses) == len(TEXTS)

    for analyzer_response in analyzer_responses:
        assert len(analyzer_response.classification) == 2
        assert "positive" in analyzer_response.classification
        assert "negative" in analyzer_response.classification
