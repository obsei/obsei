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
    labels: Optional[List[str]] = None
    label_map: Optional[Dict[str, str]] = None
    multi_class_classification: bool = True
    add_positive_negative_labels: bool = True
    aggregator_config: InferenceAggregatorConfig = Field(
        InferenceAggregatorConfig(aggregate_function=ClassificationAverageScore())
    )

    def __init__(self, **data: Any):
        super().__init__(**data)

        if self.labels is None:
            self.multi_class_classification = False
            self.add_positive_negative_labels = False


class TextClassificationAnalyzer(BaseAnalyzer):
    TYPE: str = "Classification"
    pipeline_name: str = "text-classification"
    _pipeline: Pipeline = PrivateAttr()
    _max_length: int = PrivateAttr()
    model_name_or_path: str

    def __init__(self, **data: Any):
        super().__init__(**data)
        self._pipeline = pipeline(
            self.pipeline_name,
            model=self.model_name_or_path,
            device=self._device_id,
        )

        if hasattr(self._pipeline.model.config, "max_position_embeddings"):
            self._max_length = self._pipeline.model.config.max_position_embeddings
        else:
            self._max_length = MAX_LENGTH

    def prediction_from_model(
        self,
        texts: List[str],
        analyzer_config: Optional[ClassificationAnalyzerConfig] = None,
    ) -> List[Dict[str, Any]]:
        prediction = self._pipeline(texts)
        predictions = prediction if isinstance(prediction, list) else [prediction]
        label_map = analyzer_config.label_map if analyzer_config is not None else {}
        label_map = label_map or {}
        return [
            {
                label_map.get(prediction["label"], prediction["label"]): prediction["score"]
            } for prediction in predictions
        ]

    def analyze_input(  # type: ignore[override]
        self,
        source_response_list: List[TextPayload],
        analyzer_config: Optional[ClassificationAnalyzerConfig] = None,
        **kwargs,
    ) -> List[TextPayload]:
        analyzer_output: List[TextPayload] = []

        if (
            analyzer_config is not None
            and analyzer_config.use_splitter_and_aggregator
            and analyzer_config.splitter_config
        ):
            source_response_list = self.splitter.preprocess_input(
                source_response_list,
                config=analyzer_config.splitter_config,
            )

        for batch_responses in self.batchify(source_response_list, self.batch_size):
            texts = [
                source_response.processed_text[: self._max_length]
                for source_response in batch_responses
            ]

            batch_predictions = self.prediction_from_model(texts=texts, analyzer_config=analyzer_config)

            for score_dict, source_response in zip(batch_predictions, batch_responses):
                segmented_data = {
                    "classifier_data": score_dict
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

        if (
            analyzer_config is not None
            and analyzer_config.use_splitter_and_aggregator
            and analyzer_config.aggregator_config
        ):
            analyzer_output = self.aggregator.postprocess_input(
                input_list=analyzer_output,
                config=analyzer_config.aggregator_config,
            )

        return analyzer_output


class ZeroShotClassificationAnalyzer(TextClassificationAnalyzer):
    pipeline_name: str = "zero-shot-classification"

    def prediction_from_model(
        self,
        texts: List[str],
        analyzer_config: Optional[ClassificationAnalyzerConfig] = None,
    ) -> List[Dict[str, Any]]:
        if analyzer_config is None:
            raise ValueError("analyzer_config can't be None")

        labels = analyzer_config.labels or []
        if analyzer_config.add_positive_negative_labels:
            if "positive" not in labels:
                labels.append("positive")
            if "negative" not in labels:
                labels.append("negative")

        if len(labels) == 0:
            raise ValueError("`labels` can't be empty or `add_positive_negative_labels` should be False")

        prediction = self._pipeline(
            texts, candidate_labels=labels, multi_label=analyzer_config.multi_class_classification
        )
        predictions = prediction if isinstance(prediction, list) else [prediction]

        return [dict(zip(prediction["labels"], prediction["scores"])) for prediction in predictions]

    def analyze_input(  # type: ignore[override]
        self,
        source_response_list: List[TextPayload],
        analyzer_config: Optional[ClassificationAnalyzerConfig] = None,
        **kwargs,
    ) -> List[TextPayload]:
        if analyzer_config is None:
            raise ValueError("analyzer_config can't be None")

        return super().analyze_input(
            source_response_list=source_response_list,
            analyzer_config=analyzer_config,
            **kwargs
        )
