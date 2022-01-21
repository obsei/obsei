import logging
from abc import abstractmethod
from typing import Any, Dict, List, Tuple

from pydantic import BaseModel

from obsei.payload import TextPayload

logger = logging.getLogger(__name__)


class BaseInferenceAggregateFunction(BaseModel):
    @abstractmethod
    def execute(
        self, input_list: List[TextPayload], **kwargs
    ) -> List[TextPayload]:
        pass

    @staticmethod
    def _extract_merged_parameters(
        input_list: List[TextPayload],
    ) -> Tuple[List[str], int, Dict[str, Any]]:
        document_length: int = 0
        meta: Dict[str, Any] = {}
        doc_text: List[str] = []
        # Merge meta across payload and collect score keys
        for payload in input_list:
            document_length += len(payload.processed_text)
            meta = {**meta, **payload.meta} if payload.meta else meta
            # Remove splitter key from meta
            meta.pop("splitter")
            doc_text.append(payload.processed_text)
        return doc_text, document_length, meta


class ClassificationAverageScore(BaseInferenceAggregateFunction):
    name: str = "ClassificationAverageScore"
    default_value: float = 0.0

    def execute(
        self, input_list: List[TextPayload], **kwargs
    ) -> List[TextPayload]:
        if len(input_list) == 0:
            logger.warning("Can't aggregate empty list")
            return input_list

        if not input_list[0].is_contains_classification_payload():
            logger.warning(
                "ClassificationAverage supports Classification and Sentiment Analyzers only"
            )
            return input_list

        default_value = kwargs.get("default_value", self.default_value)

        source_name = input_list[0].source_name

        doc_text, document_length, meta = self._extract_merged_parameters(input_list)

        # Perform average based on chunk length
        scores: Dict[str, float] = {}
        for payload in input_list:
            if payload.segmented_data:
                for key, value in payload.segmented_data.get("classifier_data", {}).items():
                    ratio = len(payload.processed_text) / document_length
                    scores[key] = scores.get(key, default_value) + value * ratio

        return [
            TextPayload(
                processed_text=" ".join(doc_text),
                meta=meta,
                segmented_data={
                    "aggregator_data": {
                        "avg_score": scores,
                        "aggregator_name": self.name,
                    }
                },
                source_name=source_name,
            )
        ]


class ClassificationMaxCategories(BaseInferenceAggregateFunction):
    name: str = "ClassificationMaxCategories"
    score_threshold: float = 0.5

    def execute(
        self, input_list: List[TextPayload], **kwargs
    ) -> List[TextPayload]:
        if len(input_list) == 0:
            logger.warning("Can't aggregate empty list")
            return input_list

        if not input_list[0].is_contains_classification_payload():
            logger.warning(
                "ClassificationAverage supports Classification and Sentiment Analyzers only"
            )
            return input_list

        score_threshold = kwargs.get("score_threshold", self.score_threshold)

        source_name = input_list[0].source_name

        doc_text, _, meta = self._extract_merged_parameters(input_list)

        max_scores: Dict[str, float] = {}
        category_count: Dict[str, int] = {}
        for payload in input_list:
            if payload.segmented_data:
                for key, value in payload.segmented_data.get("classifier_data", {}).items():
                    if value > score_threshold:
                        category_count[key] = category_count.get(key, 0) + 1
                        max_scores[key] = max(max_scores.get(key, 0.0), value)

        return [
            TextPayload(
                processed_text=" ".join(doc_text),
                meta=meta,
                segmented_data={
                    "aggregator_data": {
                        "category_count": category_count,
                        "max_scores": max_scores,
                        "aggregator_name": self.name,
                    }
                },
                source_name=source_name,
            )
        ]
