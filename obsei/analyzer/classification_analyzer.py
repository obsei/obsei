import logging
from typing import Any, Dict, List, Optional

from pydantic import PrivateAttr
from transformers import Pipeline, pipeline

from obsei.analyzer.base_analyzer import AnalyzerRequest, AnalyzerResponse, BaseAnalyzer, BaseAnalyzerConfig

logger = logging.getLogger(__name__)


class ClassificationAnalyzerConfig(BaseAnalyzerConfig):
    TYPE: str = "Classification"
    labels: List[str]
    multi_class_classification: Optional[bool] = True


class ZeroShotClassificationAnalyzer(BaseAnalyzer):
    _pipeline: Pipeline = PrivateAttr()
    TYPE: str = "Classification"
    model_name_or_path: str

    def __init__(self, **data: Any):
        super().__init__(**data)
        self._pipeline = pipeline("zero-shot-classification", model=self.model_name_or_path)

    def _classify_text_from_model(
        self, text: str,
        labels: List[str],
        multi_class_classification: bool = True
    ) -> Dict[str, float]:
        scores_data = self._pipeline(text, labels, multi_class=multi_class_classification)

        score_dict = {label: score for label, score in zip(scores_data["labels"], scores_data["scores"])}
        return dict(sorted(score_dict.items(), key=lambda x: x[1], reverse=True))

    def analyze_input(
        self,
        source_response_list: List[AnalyzerRequest],
        analyzer_config: ClassificationAnalyzerConfig,
        add_positive_negative_labels: Optional[bool] = True,
        **kwargs
    ) -> List[AnalyzerResponse]:
        analyzer_config = analyzer_config
        analyzer_output: List[AnalyzerResponse] = []

        labels = analyzer_config.labels or []
        if add_positive_negative_labels:
            if "positive" not in labels:
                labels.append("positive")
            if "negative" not in labels:
                labels.append("negative")

        for source_response in source_response_list:
            classification_map = self._classify_text_from_model(
                source_response.processed_text,
                labels,
                analyzer_config.multi_class_classification
            )

            analyzer_output.append(
                AnalyzerResponse(
                    processed_text=source_response.processed_text,
                    meta=source_response.meta,
                    segmented_data=classification_map,
                    source_name=source_response.source_name,
                )
            )

        return analyzer_output
