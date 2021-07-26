import logging
from typing import Any, List, Optional

from pydantic import PrivateAttr
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

from obsei.analyzer.base_analyzer import (
    BaseAnalyzer,
    BaseAnalyzerConfig,
)
from obsei.payload import TextPayload
from obsei.analyzer.classification_analyzer import (
    ClassificationAnalyzerConfig,
    ZeroShotClassificationAnalyzer,
)

logger = logging.getLogger(__name__)


class VaderSentimentAnalyzer(BaseAnalyzer):
    _model: SentimentIntensityAnalyzer = PrivateAttr()
    TYPE: str = "Sentiment"

    def __init__(self, **data: Any):
        super().__init__(**data)
        self._model = SentimentIntensityAnalyzer()

    def _get_sentiment_score_from_vader(self, text: str) -> float:
        scores = self._model.polarity_scores(text)
        return scores["compound"]

    def analyze_input(
        self,
        source_response_list: List[TextPayload],
        analyzer_config: BaseAnalyzerConfig = None,
        **kwargs,
    ) -> List[TextPayload]:
        analyzer_output: List[TextPayload] = []

        for batch_responses in self.batchify(source_response_list, self.batch_size):
            for source_response in batch_responses:
                classification_map = {}
                sentiment_value = self._get_sentiment_score_from_vader(
                    source_response.processed_text
                )
                if sentiment_value < 0.0:
                    classification_map["negative"] = -sentiment_value
                    classification_map["positive"] = (
                        1.0 - classification_map["negative"]
                    )
                else:
                    classification_map["positive"] = sentiment_value
                    classification_map["negative"] = (
                        1.0 - classification_map["positive"]
                    )

                segmented_data = {"classifier_data": classification_map}
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

        return analyzer_output


class TransformersSentimentAnalyzerConfig(ClassificationAnalyzerConfig):
    TYPE: str = "Sentiment"
    labels: List[str] = ["positive", "negative"]
    multi_class_classification: bool = False


class TransformersSentimentAnalyzer(ZeroShotClassificationAnalyzer):
    def analyze_input(  # type: ignore[override]
        self,
        source_response_list: List[TextPayload],
        analyzer_config: Optional[TransformersSentimentAnalyzerConfig] = None,
        **kwargs,
    ) -> List[TextPayload]:
        return super().analyze_input(
            source_response_list=source_response_list,
            analyzer_config=analyzer_config,
            add_positive_negative_labels=True,
            **kwargs,
        )
