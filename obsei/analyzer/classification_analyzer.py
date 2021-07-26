import logging
from typing import Any, Dict, List, Optional

from pydantic import Field, PrivateAttr
from transformers import Pipeline, pipeline

from obsei.analyzer.base_analyzer import (
    BaseAnalyzer,
    BaseAnalyzerConfig,
    MAX_LENGTH,
)
from obsei.payload import TextPayload
from obsei.postprocessor.inference_aggregator import InferenceAggregatorConfig
from obsei.postprocessor.inference_aggregator_function import ClassificationAverageScore

logger = logging.getLogger(__name__)


class ClassificationAnalyzerConfig(BaseAnalyzerConfig):
    TYPE: str = "Classification"
    labels: List[str]
    multi_class_classification: bool = True
    aggregator_config: InferenceAggregatorConfig = Field(
        InferenceAggregatorConfig(
            aggregate_function=ClassificationAverageScore()
        )
    )


class ZeroShotClassificationAnalyzer(BaseAnalyzer):
    _pipeline: Pipeline = PrivateAttr()
    _max_length: int = PrivateAttr()
    TYPE: str = "Classification"
    model_name_or_path: str

    def __init__(self, **data: Any):
        super().__init__(**data)
        self._pipeline = pipeline(
            "zero-shot-classification",
            model=self.model_name_or_path,
            device=self._device_id,
        )

        if hasattr(self._pipeline.model.config, "max_position_embeddings"):
            self._max_length = self._pipeline.model.config.max_position_embeddings
        else:
            self._max_length = MAX_LENGTH

    def _prediction_from_model(
        self,
        texts: List[str],
        labels: List[str],
        multi_class_classification: bool = True,
    ) -> List[Dict[str, Any]]:
        prediction = self._pipeline(
            texts, labels, multi_label=multi_class_classification
        )
        return prediction if isinstance(prediction, list) else [prediction]

    def analyze_input(  # type: ignore[override]
        self,
        source_response_list: List[TextPayload],
        analyzer_config: Optional[ClassificationAnalyzerConfig] = None,
        **kwargs,
    ) -> List[TextPayload]:
        if analyzer_config is None:
            raise ValueError("analyzer_config can't be None")

        analyzer_output: List[TextPayload] = []

        labels = analyzer_config.labels or []
        add_positive_negative_labels = kwargs.get("add_positive_negative_labels", True)
        if add_positive_negative_labels:
            if "positive" not in labels:
                labels.append("positive")
            if "negative" not in labels:
                labels.append("negative")

        if analyzer_config.use_splitter_and_aggregator and analyzer_config.splitter_config:
            source_response_list = self.splitter.preprocess_input(
                source_response_list,
                config=analyzer_config.splitter_config,
            )

        for batch_responses in self.batchify(source_response_list, self.batch_size):
            texts = [
                source_response.processed_text[: self._max_length]
                for source_response in batch_responses
            ]

            batch_predictions = self._prediction_from_model(
                texts,
                labels,
                analyzer_config.multi_class_classification,
            )

            for prediction, source_response in zip(batch_predictions, batch_responses):
                score_dict = {
                    label: score
                    for label, score in zip(prediction["labels"], prediction["scores"])
                }

                segmented_data = {
                    "classifier_data": dict(
                        sorted(score_dict.items(), key=lambda x: x[1], reverse=True)
                    )
                }

                if source_response.segmented_data:
                    segmented_data = {
                        **segmented_data,
                        **source_response.segmented_data,
                    }

                analyzer_output.append(
                    TextPayload(
                        processed_text=source_response.processed_text,
                        meta=source_response.meta,
                        segmented_data=segmented_data,
                        source_name=source_response.source_name,
                    )
                )

        if analyzer_config.use_splitter_and_aggregator and analyzer_config.aggregator_config:
            analyzer_output = self.aggregator.postprocess_input(
                input_list=analyzer_output,
                config=analyzer_config.aggregator_config,
            )

        return analyzer_output
