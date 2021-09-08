import pytest

from obsei.analyzer.classification_analyzer import ClassificationAnalyzerConfig
from obsei.payload import TextPayload
from obsei.postprocessor.inference_aggregator import InferenceAggregatorConfig
from obsei.postprocessor.inference_aggregator_function import (
    ClassificationAverageScore,
    ClassificationMaxCategories,
)
from obsei.preprocessor.text_splitter import TextSplitterConfig

GOOD_TEXT = """If anyone is interested... these are our hosts. I can’t recommend them enough, Abc & Pbc.

The unit is just lovely, you go to sleep & wake up to this incredible place, and you have use of a Weber grill and a ridiculously indulgent hot-tub under the stars"""

BAD_TEXT = """I had the worst experience ever with XYZ in Egypt. Bad Cars, asking to pay in cash,  do not have enough fuel,  do not open AC,  wait far away from my location until the trip is cancelled,  call and ask about the destination then cancel, and more. Worst service."""

MIXED_TEXT = """I am mixed"""

TEXTS = [GOOD_TEXT, BAD_TEXT, MIXED_TEXT]

BUY_INTENT = """I am interested in this style of PGN-ES-D-6150 /Direct drive energy saving servo motor price and in doing business with you. Could you please send me the quotation"""

SELL_INTENT = """Black full body massage chair for sale."""

BUY_SELL_TEXTS = [BUY_INTENT, SELL_INTENT]


def test_zero_shot_analyzer(zero_shot_analyzer):
    labels = ["facility", "food", "comfortable", "positive", "negative"]

    source_responses = [
        TextPayload(processed_text=text, source_name="sample") for text in TEXTS
    ]
    analyzer_responses = zero_shot_analyzer.analyze_input(
        source_response_list=source_responses,
        analyzer_config=ClassificationAnalyzerConfig(labels=labels),
    )

    assert len(analyzer_responses) == len(TEXTS)

    for analyzer_response in analyzer_responses:
        assert len(analyzer_response.segmented_data["classifier_data"]) == len(labels)
        assert "positive" in analyzer_response.segmented_data["classifier_data"]
        assert "negative" in analyzer_response.segmented_data["classifier_data"]


@pytest.mark.parametrize(
    "label_map, expected", [
        (None, ["LABEL_1", "LABEL_0"]),
        ({"LABEL_1": "Buy", "LABEL_0": "Sell"}, ["Buy", "Sell"])
    ]
)
def test_text_classification_analyzer(text_classification_analyzer, label_map, expected):
    source_responses = [
        TextPayload(processed_text=text, source_name="sample")
        for text in BUY_SELL_TEXTS
    ]
    analyzer_responses = text_classification_analyzer.analyze_input(
        source_response_list=source_responses,
        analyzer_config=ClassificationAnalyzerConfig(
            label_map=label_map,
        ),
    )

    assert len(analyzer_responses) == len(BUY_SELL_TEXTS)

    for analyzer_response in analyzer_responses:
        assert analyzer_response.segmented_data["classifier_data"] is not None
        assert analyzer_response.segmented_data["classifier_data"].keys() <= set(expected)


@pytest.mark.parametrize(
    "aggregate_function", [ClassificationAverageScore(), ClassificationMaxCategories()]
)
def test_classification_analyzer_with_splitter_aggregator(
    aggregate_function, zero_shot_analyzer
):
    labels = ["facility", "food", "comfortable", "positive", "negative"]

    source_responses = [
        TextPayload(processed_text=text, source_name="sample") for text in TEXTS
    ]
    analyzer_responses = zero_shot_analyzer.analyze_input(
        source_response_list=source_responses,
        analyzer_config=ClassificationAnalyzerConfig(
            labels=labels,
            use_splitter_and_aggregator=True,
            splitter_config=TextSplitterConfig(max_split_length=50),
            aggregator_config=InferenceAggregatorConfig(
                aggregate_function=aggregate_function
            ),
        ),
    )

    assert len(analyzer_responses) == len(TEXTS)

    for analyzer_response in analyzer_responses:
        assert "aggregator_data" in analyzer_response.segmented_data


def test_vader_analyzer(vader_analyzer):
    source_responses = [
        TextPayload(processed_text=text, source_name="sample") for text in TEXTS
    ]
    analyzer_responses = vader_analyzer.analyze_input(
        source_response_list=source_responses
    )

    assert len(analyzer_responses) == len(TEXTS)

    for analyzer_response in analyzer_responses:
        assert len(analyzer_response.segmented_data["classifier_data"]) == 2
        assert "positive" in analyzer_response.segmented_data["classifier_data"]
        assert "negative" in analyzer_response.segmented_data["classifier_data"]


def test_trf_ner_analyzer(trf_ner_analyzer):
    source_responses = [
        TextPayload(
            processed_text="My name is Sam and I live in Berlin, Germany.",
            source_name="sample",
        )
    ]
    analyzer_responses = trf_ner_analyzer.analyze_input(
        source_response_list=source_responses,
    )
    assert len(analyzer_responses) == 1

    entities = analyzer_responses[0].segmented_data["ner_data"]
    matched_count = 0
    for entity in entities:
        if entity["word"] == "Sam" and entity["entity_group"] == "PER":
            matched_count = matched_count + 1
        elif entity["word"] == "Berlin" and entity["entity_group"] == "LOC":
            matched_count = matched_count + 1
        elif entity["word"] == "Germany" and entity["entity_group"] == "LOC":
            matched_count = matched_count + 1

    assert matched_count == 3


def test_spacy_ner_analyzer(spacy_ner_analyzer):
    source_responses = [
        TextPayload(
            processed_text="My name is Sam and I live in Berlin, Germany.",
            source_name="sample",
        )
    ]
    analyzer_responses = spacy_ner_analyzer.analyze_input(
        source_response_list=source_responses,
    )
    assert len(analyzer_responses) == 1

    entities = analyzer_responses[0].segmented_data["ner_data"]
    matched_count = 0
    for entity in entities:
        if entity["word"] == "Sam" and entity["entity_group"] == "PERSON":
            matched_count = matched_count + 1
        elif entity["word"] == "Berlin" and entity["entity_group"] == "GPE":
            matched_count = matched_count + 1
        elif entity["word"] == "Germany" and entity["entity_group"] == "GPE":
            matched_count = matched_count + 1

    assert matched_count == 3
