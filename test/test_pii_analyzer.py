from obsei.analyzer.base_analyzer import AnalyzerRequest
from obsei.analyzer.pii_analyzer import PresidioPIIAnalyzerConfig

text_to_anonymize = "His name is Mr. Jones and his phone number is 212-555-5555"
PII_LIST = ["Jones", "212-555-5555"]
TEXTS = [text_to_anonymize]


def test_pii_analyzer_replace_original(pii_analyzer):
    analyzer_config = PresidioPIIAnalyzerConfig(
        analyze_only=False,
        return_decision_process=True,
        replace_original_text=True
    )

    source_responses = [AnalyzerRequest(processed_text=text, source_name="sample") for text in TEXTS]
    analyzer_responses = pii_analyzer.analyze_input(
        source_response_list=source_responses,
        analyzer_config=analyzer_config
    )
    assert len(analyzer_responses) == len(TEXTS)

    for text, analyzer_response in zip(TEXTS, analyzer_responses):

        assert analyzer_response.segmented_data is not None
        assert analyzer_response.segmented_data["analyzer_result"] is not None
        assert analyzer_response.segmented_data["anonymized_result"] is not None

        assert text != analyzer_response.analyzer_response.segmented_data["anonymized_result"]["text"]
        for pii_info in PII_LIST:
            assert pii_info not in analyzer_response.analyzer_response.segmented_data["anonymized_result"]["text"]

        anonymized_result = analyzer_response.analyzer_response.segmented_data["anonymized_result"]
        assert anonymized_result["text"] == analyzer_response.processed_text


def test_pii_analyzer_not_replace_original(pii_analyzer):
    analyzer_config = PresidioPIIAnalyzerConfig(
        analyze_only=False,
        return_decision_process=True,
        replace_original_text=False
    )

    source_responses = [AnalyzerRequest(processed_text=text, source_name="sample") for text in TEXTS]
    analyzer_responses = pii_analyzer.analyze_input(
        source_response_list=source_responses,
        analyzer_config=analyzer_config
    )
    assert len(analyzer_responses) == len(TEXTS)

    for text, analyzer_response in zip(TEXTS, analyzer_responses):

        assert analyzer_response.segmented_data is not None
        assert analyzer_response.segmented_data["analyzer_result"] is not None
        assert analyzer_response.segmented_data["anonymized_result"] is not None

        assert text != analyzer_response.analyzer_response.segmented_data["anonymized_result"]["text"]
        for pii_info in PII_LIST:
            assert pii_info not in analyzer_response.analyzer_response.segmented_data["anonymized_result"]["text"]

        anonymized_result = analyzer_response.analyzer_response.segmented_data["anonymized_result"]
        assert anonymized_result["text"] != analyzer_response.processed_text
        assert text == analyzer_response.processed_text


def test_pii_analyzer_analyze_only(pii_analyzer):
    analyzer_config = PresidioPIIAnalyzerConfig(
        analyze_only=True,
        return_decision_process=True
    )

    source_responses = [AnalyzerRequest(processed_text=text, source_name="sample") for text in TEXTS]
    analyzer_responses = pii_analyzer.analyze_input(
        source_response_list=source_responses,
        analyzer_config=analyzer_config
    )
    assert len(analyzer_responses) == len(TEXTS)

    for text, analyzer_response in zip(TEXTS, analyzer_responses):

        assert analyzer_response.segmented_data is not None
        assert analyzer_response.segmented_data["analyzer_result"] is not None
        assert analyzer_response.segmented_data["anonymized_result"] is None

        assert text == analyzer_response.processed_text
