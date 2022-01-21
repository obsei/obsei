from obsei.payload import TextPayload
from obsei.analyzer.pii_analyzer import PresidioPIIAnalyzerConfig

text_to_anonymize = "His name is Mr. Jones. His phone number is 212-555-5555 and email is jones@email.com"
PII_LIST = ["Jones", "212-555-5555", "jones@email.com"]
TEXTS = [text_to_anonymize]


def test_pii_analyzer_replace_original(pii_analyzer):
    analyzer_config = PresidioPIIAnalyzerConfig(
        analyze_only=False, return_decision_process=True, replace_original_text=True
    )

    source_responses = [
        TextPayload(processed_text=text, source_name="sample") for text in TEXTS
    ]
    analyzer_responses = pii_analyzer.analyze_input(
        source_response_list=source_responses, analyzer_config=analyzer_config
    )
    assert len(analyzer_responses) == len(TEXTS)

    for text, analyzer_response in zip(TEXTS, analyzer_responses):

        assert analyzer_response.segmented_data is not None
        assert analyzer_response.segmented_data["pii_data"] is not None
        assert analyzer_response.segmented_data["pii_data"]["analyzer_result"] is not None
        assert analyzer_response.segmented_data["pii_data"]["anonymized_result"] is not None
        assert analyzer_response.segmented_data["pii_data"]["anonymized_text"] is not None

        for pii_info in PII_LIST:
            assert pii_info not in analyzer_response.segmented_data["pii_data"]["anonymized_text"]

        assert (
            analyzer_response.segmented_data["pii_data"]["anonymized_text"]
            == analyzer_response.processed_text
        )
        assert analyzer_response.segmented_data["pii_data"]["anonymized_text"] != text


def test_pii_analyzer_not_replace_original(pii_analyzer):
    analyzer_config = PresidioPIIAnalyzerConfig(
        analyze_only=False, return_decision_process=True, replace_original_text=False
    )

    source_responses = [
        TextPayload(processed_text=text, source_name="sample") for text in TEXTS
    ]
    analyzer_responses = pii_analyzer.analyze_input(
        source_response_list=source_responses, analyzer_config=analyzer_config
    )
    assert len(analyzer_responses) == len(TEXTS)

    for text, analyzer_response in zip(TEXTS, analyzer_responses):

        assert analyzer_response.segmented_data is not None
        assert analyzer_response.segmented_data["pii_data"] is not None
        assert analyzer_response.segmented_data["pii_data"]["analyzer_result"] is not None
        assert analyzer_response.segmented_data["pii_data"]["anonymized_result"] is not None
        assert analyzer_response.segmented_data["pii_data"]["anonymized_text"] is not None

        for pii_info in PII_LIST:
            assert pii_info not in analyzer_response.segmented_data["pii_data"]["anonymized_text"]

        assert analyzer_response.processed_text == text
        assert analyzer_response.segmented_data["pii_data"]["anonymized_text"] != text


def test_pii_analyzer_analyze_only(pii_analyzer):
    analyzer_config = PresidioPIIAnalyzerConfig(
        analyze_only=True, return_decision_process=True
    )

    source_responses = [
        TextPayload(processed_text=text, source_name="sample") for text in TEXTS
    ]
    analyzer_responses = pii_analyzer.analyze_input(
        source_response_list=source_responses, analyzer_config=analyzer_config
    )
    assert len(analyzer_responses) == len(TEXTS)

    for text, analyzer_response in zip(TEXTS, analyzer_responses):

        assert analyzer_response.segmented_data is not None
        assert analyzer_response.segmented_data["pii_data"] is not None
        assert analyzer_response.segmented_data["pii_data"]["analyzer_result"] is not None
        assert analyzer_response.segmented_data["pii_data"]["anonymized_result"] is None

        assert text == analyzer_response.processed_text
