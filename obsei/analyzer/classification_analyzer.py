import logging
from typing import Any, Dict, List, Tuple, Optional, Generator

from pydantic import PrivateAttr
from transformers import Pipeline, pipeline

from obsei.analyzer.base_analyzer import (
    BaseAnalyzer,
    BaseAnalyzerConfig,
)
from obsei.payload import TextPayload

logger = logging.getLogger(__name__)


class ClassificationAnalyzerConfig(BaseAnalyzerConfig):
    TYPE: str = "Classification"
    labels: List[str]
    multi_class_classification: bool = True


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
            self._max_length = 510

    def _classify_text_from_model(
        self,
        texts: List[str],
        labels: List[str],
        multi_class_classification: bool = True,
    ) -> List[Dict[str, Any]]:
        prediction = self._pipeline(
            texts, labels, multi_label=multi_class_classification
        )
        return prediction if isinstance(prediction, list) else [prediction]

    def _batchify(
        self,
        texts: List[str],
        batch_size: int,
        source_response_list: List[TextPayload],
    ) -> Generator[Tuple[List[str], List[TextPayload]], None, None]:
        for index in range(0, len(texts), batch_size):
            yield (
                texts[index : index + batch_size],
                source_response_list[index : index + batch_size],
            )

    def analyze_input(  # type: ignore[override]
        self,
        source_response_list: List[TextPayload],
        analyzer_config: Optional[ClassificationAnalyzerConfig] = None,
        **kwargs,
    ) -> List[TextPayload]:
        if analyzer_config is None:
            raise ValueError("analyzer_config can't be None")

        analyzer_output: List[TextPayload] = []
        add_positive_negative_labels = kwargs.get("add_positive_negative_labels", True)

        texts = [
            source_response.processed_text[: self._max_length]
            if len(source_response.processed_text) > self._max_length
            else source_response.processed_text
            for source_response in source_response_list
        ]

        labels = analyzer_config.labels or []
        if add_positive_negative_labels:
            if "positive" not in labels:
                labels.append("positive")
            if "negative" not in labels:
                labels.append("negative")

        for batch_texts, batch_source_response in self._batchify(
            texts, self.batch_size, source_response_list
        ):
            batch_predictions = self._classify_text_from_model(
                batch_texts,
                labels,
                analyzer_config.multi_class_classification,
            )
            for prediction, source_response in zip(
                batch_predictions, batch_source_response
            ):
                score_dict = {
                    label: score
                    for label, score in zip(prediction["labels"], prediction["scores"])
                }

                classification_map = dict(
                    sorted(score_dict.items(), key=lambda x: x[1], reverse=True)
                )
                analyzer_output.append(
                    TextPayload(
                        processed_text=source_response.processed_text,
                        meta=source_response.meta,
                        segmented_data=classification_map,
                        source_name=source_response.source_name,
                    )
                )

        return analyzer_output
