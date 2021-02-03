import logging
from typing import Any, List

from pydantic import PrivateAttr
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

from obsei.analyzer.base_analyzer import AnalyzerRequest, AnalyzerResponse, BaseAnalyzer, BaseAnalyzerConfig
from obsei.analyzer.classification_analyzer import ClassificationAnalyzerConfig, ZeroShotClassificationAnalyzer

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
            source_response_list: List[AnalyzerRequest],
            analyzer_config: BaseAnalyzerConfig = None,
            **kwargs
    ) -> List[AnalyzerResponse]:
        analyzer_output: List[AnalyzerResponse] = []

        for source_response in source_response_list:
            classification_map = {}
            sentiment_value = self._get_sentiment_score_from_vader(source_response.processed_text)
            if sentiment_value < 0.0:
                classification_map["negative"] = -sentiment_value
                classification_map["positive"] = 1.0 - classification_map["negative"]
            else:
                classification_map["positive"] = sentiment_value
                classification_map["negative"] = 1.0 - classification_map["positive"]

            analyzer_output.append(
                AnalyzerResponse(
                    processed_text=source_response.processed_text,
                    meta=source_response.meta,
                    segmented_data=classification_map,
                    source_name=source_response.source_name,
                )
            )

        return analyzer_output


class TransformersSentimentAnalyzerConfig(ClassificationAnalyzerConfig):
    TYPE: str = "Sentiment"
    labels: List[str] = ["positive", "negative"]
    multi_class_classification: bool = False


class TransformersSentimentAnalyzer(ZeroShotClassificationAnalyzer):
    def analyze_input(
            self,
            source_response_list: List[AnalyzerRequest],
            analyzer_config: TransformersSentimentAnalyzerConfig,
            **kwargs
    ) -> List[AnalyzerResponse]:
        return super().analyze_input(
            source_response_list=source_response_list,
            analyzer_config=analyzer_config,
            add_positive_negative_labels=True,
            **kwargs
        )
