import logging
from typing import Any, Dict, List, Optional

from pydantic import PrivateAttr
from transformers import AutoModelForTokenClassification, AutoTokenizer, Pipeline, pipeline

from obsei.analyzer.base_analyzer import AnalyzerRequest, AnalyzerResponse, BaseAnalyzer, BaseAnalyzerConfig

logger = logging.getLogger(__name__)


class NERAnalyzer(BaseAnalyzer):
    _pipeline: Pipeline = PrivateAttr()
    TYPE: str = "NER"
    model_name_or_path: str
    tokenizer_name: Optional[str] = None
    grouped_entities: Optional[bool] = True

    def __init__(self, **data: Any):
        super().__init__(**data)

        model = AutoModelForTokenClassification.from_pretrained(self.model_name_or_path)
        if self.tokenizer_name:
            tokenizer = AutoTokenizer.from_pretrained(self.tokenizer_name, use_fast=True)
        else:
            tokenizer = None

        self._pipeline = pipeline(
            'ner',
            model=model,
            tokenizer=tokenizer,
            grouped_entities=self.grouped_entities
        )

    def _classify_text_from_model(self, text: str) -> Dict[str, float]:
        return self._pipeline(text)

    def analyze_input(
        self,
        source_response_list: List[AnalyzerRequest],
        analyzer_config: Optional[BaseAnalyzerConfig] = None,
        **kwargs
    ) -> List[AnalyzerResponse]:
        analyzer_output: List[AnalyzerResponse] = []

        for source_response in source_response_list:
            ner_list = self._classify_text_from_model(source_response.processed_text)

            analyzer_output.append(
                AnalyzerResponse(
                    processed_text=source_response.processed_text,
                    meta=source_response.meta,
                    segmented_data={"data": ner_list},
                    source_name=source_response.source_name,
                )
            )

        return analyzer_output
