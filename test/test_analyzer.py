import pytest

from obsei.analyzer.classification_analyzer import ClassificationAnalyzerConfig
from obsei.analyzer.topic_analyzer import TopicClassificationAnalyzer, TopicAnalyzerConfig
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

TOPIC_DOC = ''' Artificial intelligence (AI) is intelligence demonstrated by machines, as opposed to the natural intelligence displayed by humans or animals. Leading AI textbooks define the field as the study of "intelligent agents": any system that perceives its environment and takes actions that maximize its chance of achieving its goals.[a] Some popular accounts use the term "artificial intelligence" to describe machines that mimic "cognitive" functions that humans associate with the human mind, such as "learning" and "problem solving", however this definition is rejected by major AI researchers.

AI applications include advanced web search engines (i.e. Google), recommendation systems (used by YouTube, Amazon and Netflix), understanding human speech (such as Siri or Alexa), self-driving cars (e.g. Tesla), and competing at the highest level in strategic game systems (such as chess and Go). As machines become increasingly capable, tasks considered to require "intelligence" are often removed from the definition of AI, a phenomenon known as the AI effect. For instance, optical character recognition is frequently excluded from things considered to be AI, having become a routine technology.

Artificial intelligence was founded as an academic discipline in 1956, and in the years since has experienced several waves of optimism, followed by disappointment and the loss of funding (known as an "AI winter"), followed by new approaches, success and renewed funding. AI research has tried and discarded many different approaches during its lifetime, including simulating the brain, modeling human problem solving, formal logic, large databases of knowledge and imitating animal behavior. In the first decades of the 21st century, highly mathematical statistical machine learning has dominated the field, and this technique has proved highly successful, helping to solve many challenging problems throughout industry and academia. 
'''


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


@pytest.mark.parametrize("method", ["LDA", "LDA_BERT", "BERT"])
def test_topic_analyzer(method):
    source_responses = [
        TextPayload(
            processed_text=TOPIC_DOC,
            source_name="sample",
        )
    ]

    analyzer = TopicClassificationAnalyzer(
        model_name_or_path="sentence-transformers/paraphrase-xlm-r-multilingual-v1"
    )

    topics = analyzer.analyze_input(
        analyzer_config=TopicAnalyzerConfig(method=method),
        source_response_list=source_responses,
    )

    for topic in topics:
        print(f'===> {method}: {topic.__dict__}')

    assert len(topics) > 0
