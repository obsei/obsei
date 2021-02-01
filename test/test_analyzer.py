from obsei.analyzer.classification_analyzer import ClassificationAnalyzerConfig
from obsei.analyzer.base_analyzer import AnalyzerRequest

GOOD_TEXT = '''If anyone is interested... these are our hosts. I can’t recommend them enough, Abc & Pbc.

The unit is just lovely, you go to sleep & wake up to this incredible place, and you have use of a Weber grill and a ridiculously indulgent hot-tub under the stars'''

BAD_TEXT = '''I had the worst experience ever with XYZ in Egypt. Bad Cars, asking to pay in cash,  do not have enough fuel,  do not open AC,  wait far away from my location until the trip is cancelled,  call and ask about the destination then cancel, and more. Worst service.'''

MIXED_TEXT = '''I am mixed'''

TEXTS = [GOOD_TEXT, BAD_TEXT, MIXED_TEXT]


def test_zero_shot_analyzer(zero_shot_analyzer):
    labels = ["facility", "food", "comfortable", "positive", "negative"]

    source_responses = [AnalyzerRequest(processed_text=text, source_name="sample") for text in TEXTS]
    analyzer_responses = zero_shot_analyzer.analyze_input(
        source_response_list=source_responses,
        analyzer_config=ClassificationAnalyzerConfig(
            labels=labels
        )
    )

    assert len(analyzer_responses) == len(TEXTS)

    for analyzer_response in analyzer_responses:
        assert len(analyzer_response.segmented_data) == len(labels)
        assert "positive" in analyzer_response.segmented_data
        assert "negative" in analyzer_response.segmented_data


def test_vader_analyzer(vader_analyzer):
    source_responses = [AnalyzerRequest(processed_text=text, source_name="sample") for text in TEXTS]
    analyzer_responses = vader_analyzer.analyze_input(
        source_response_list=source_responses
    )

    assert len(analyzer_responses) == len(TEXTS)

    for analyzer_response in analyzer_responses:
        assert len(analyzer_response.segmented_data) == 2
        assert "positive" in analyzer_response.segmented_data
        assert "negative" in analyzer_response.segmented_data


def test_ner_analyzer(ner_analyzer):
    source_responses = [
        AnalyzerRequest(
            processed_text="My name is Lalit and I live in Berlin, Germany.",
            source_name="sample"
        )
    ]
    analyzer_responses = ner_analyzer.analyze_input(
        source_response_list=source_responses
    )

    assert len(analyzer_responses) == 1

    entities = analyzer_responses[0].segmented_data["data"]
    matched_count = 0
    for entity in entities:
        if entity["word"] == 'Lalit' and entity["entity_group"] == "PER":
            matched_count = matched_count + 1
        elif entity["word"] == 'Berlin' and entity["entity_group"] == "LOC":
            matched_count = matched_count + 1
        elif entity["word"] == 'Germany' and entity["entity_group"] == "LOC":
            matched_count = matched_count + 1

    assert matched_count == 3
