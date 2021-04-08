from obsei.analyzer.base_analyzer import AnalyzerRequest
from obsei.analyzer.pii_analyzer import PresidioPIIAnalyzerConfig

text_to_anonymize = "His name is Mr. Jones and his phone number is 212-555-5555"
PII_LIST = ["Jones", "212-555-5555"]
TEXTS = [text_to_anonymize]

analyzer_config = PresidioPIIAnalyzerConfig(
    analyze_only=False,
    return_decision_process=True
)


def test_pii_analyzer(pii_analyzer):
    source_responses = [AnalyzerRequest(processed_text=text, source_name="sample") for text in TEXTS]
    analyzer_responses = pii_analyzer.analyze_input(
        source_response_list=source_responses,
        analyzer_config=analyzer_config
    )
    assert len(analyzer_responses) == len(TEXTS)

    for text, analyzer_response in zip(TEXTS, analyzer_responses):
        assert text != analyzer_response.processed_text
        for pii_info in PII_LIST:
            assert pii_info not in text
