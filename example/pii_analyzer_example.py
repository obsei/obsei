import logging
import sys

from obsei.payload import TextPayload
from obsei.analyzer.pii_analyzer import (
    PresidioEngineConfig,
    PresidioModelConfig,
    PresidioPIIAnalyzer,
    PresidioPIIAnalyzerConfig,
)

logger = logging.getLogger(__name__)
logging.basicConfig(stream=sys.stdout, level=logging.INFO)

analyzer_config = PresidioPIIAnalyzerConfig(
    analyze_only=False, return_decision_process=True
)
analyzer = PresidioPIIAnalyzer(
    engine_config=PresidioEngineConfig(
        nlp_engine_name="spacy",
        models=[PresidioModelConfig(model_name="en_core_web_lg", lang_code="en")],
    )
)

text_to_anonymize = "His name is Mr. Jones and his phone number is 212-555-5555"

analyzer_results = analyzer.analyze_input(
    source_response_list=[TextPayload(processed_text=text_to_anonymize)],
    analyzer_config=analyzer_config,
)

for analyzer_result in analyzer_results:
    logging.info(analyzer_result.to_dict())
