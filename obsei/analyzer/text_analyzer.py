import logging
from typing import Any, Dict, List, Optional

from pydantic import BaseModel

logger = logging.getLogger(__name__)


class AnalyzerConfig(BaseModel):
    TYPE: str = "Classification"
    labels: List[str] = ["positive", "negative"]
    use_sentiment_model: bool = False
    multi_class_classification: bool = True


class AnalyzerRequest:
    def __init__(
        self,
        processed_text: str,
        source_name: str = "Undefined",
        meta: Optional[Dict[str, Any]] = None,
    ):
        self.processed_text = processed_text
        self.meta = meta
        self.source_name = source_name


class AnalyzerResponse:
    def __init__(
        self,
        processed_text: str,
        classification: Dict[str, float] = None,
        meta: Dict[str, Any] = None,
        source_name: str = None
    ):
        self.classification = classification
        self.processed_text = processed_text
        self.meta = meta
        self.source_name = source_name

    def to_dict(self):
        return {
            "processed_text": self.processed_text,
            "classification": self.classification,
            "meta": self.meta,
            "source_name": self.source_name
        }


class TextAnalyzer:
    def __init__(
            self,
            # Model names: joeddav/xlm-roberta-large-xnli, facebook/bart-large-mnli
            model_name_or_path: str = None,
            initialize_model: bool = False,
            analyzer_config: AnalyzerConfig = None,
    ):
        self.classifier_model_name = model_name_or_path

        self.analyzer_config = analyzer_config or AnalyzerConfig(use_sentiment_model=False)

        if initialize_model is True or self.classifier_model_name is not None:
            from transformers import pipeline
            self.classifier_model = pipeline("zero-shot-classification", model=model_name_or_path)
            self.vader_sentiment_analyzer = None
        else:
            from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
            self.vader_sentiment_analyzer = SentimentIntensityAnalyzer()
            self.sentiment_model = None

    def _init_classifier_model(self, classifier_model_name: str):
        if self.classifier_model is not None:
            raise AttributeError("Classifier already initialized")

        from transformers import pipeline
        self.classifier_model = pipeline("zero-shot-classification", model=classifier_model_name)

    def init_vader_sentiment_analyzer(self):
        if self.vader_sentiment_analyzer is not None:
            raise AttributeError("Classifier already initialized")

        from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
        self.vader_sentiment_analyzer = SentimentIntensityAnalyzer()

    def _get_sentiment_score_from_vader(self, text: str) -> float:
        if self.vader_sentiment_analyzer is None:
            self.init_vader_sentiment_analyzer()

        scores = self.vader_sentiment_analyzer.polarity_scores(text)
        return scores["compound"]

    def _classify_text_from_model(
            self, text: str,
            labels: List[str],
            multi_class_classification: bool = True
    ) -> Dict[str, float]:
        if self.classifier_model is None:
            self._init_classifier_model(self.classifier_model_name)

        scores_data = self.classifier_model(text, labels, multi_class=multi_class_classification)

        score_dict = {label: score for label, score in zip(scores_data["labels"], scores_data["scores"])}
        return dict(sorted(score_dict.items(), key=lambda x: x[1], reverse=True))

    def analyze_input(
        self,
        source_response_list: List[AnalyzerRequest],
        analyzer_config: AnalyzerConfig = None,
        **kwargs
    ) -> List[AnalyzerResponse]:
        analyzer_config = analyzer_config or self.analyzer_config
        analyzer_output: List[AnalyzerResponse] = []

        labels = analyzer_config.labels or []
        if "positive" not in labels:
            labels.append("positive")
        if "negative" not in labels:
            labels.append("negative")

        for source_response in source_response_list:
            classification_map = {}
            if not analyzer_config.use_sentiment_model:
                sentiment_value = self._get_sentiment_score_from_vader(source_response.processed_text)
                if sentiment_value < 0.0:
                    classification_map["negative"] = -sentiment_value
                    classification_map["positive"] = 1.0 - classification_map["negative"]
                else:
                    classification_map["positive"] = sentiment_value
                    classification_map["negative"] = 1.0 - classification_map["positive"]
            else:
                classification_map = self._classify_text_from_model(
                    source_response.processed_text,
                    labels,
                    analyzer_config.multi_class_classification
                )

            analyzer_output.append(
                AnalyzerResponse(
                    processed_text=source_response.processed_text,
                    meta=source_response.meta,
                    classification=classification_map,
                    source_name=source_response.source_name,
                )
            )

        return analyzer_output
