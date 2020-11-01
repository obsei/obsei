import logging
from typing import Any, Dict, List, Optional

from obsei.source.base_source import SourceResponse

logger = logging.getLogger(__name__)


class AnalyzerResponse:
    def __init__(
        self,
        text: str,
        sentiment_value: float,
        sentiment_type: str,
        classification_map: Dict[str, float] = None,
        meta_information: Dict[str, Any] = None,
    ):
        self.sentiment_value = sentiment_value
        self.sentiment_type = sentiment_type
        self.classification_map = classification_map
        self.text = text
        self.meta_information = meta_information

    def to_dict(self):
        return {
            "text": self.text,
            "sentiment_value": self.sentiment_value,
            "sentiment_type": self.sentiment_type,
            "classification_map": self.classification_map,
            "meta_information": self.meta_information,
        }


class TextAnalyzer:
    def __init__(
            self,
            # Model names: joeddav/xlm-roberta-large-xnli, facebook/bart-large-mnli
            classifier_model_name: Optional[str] = None,
            multi_class_classification: Optional[bool] = True,
            initialize_sentiment_model: Optional[bool] = False,
    ):
        self.multi_class_classification = multi_class_classification
        self.classifier_model_name = classifier_model_name

        if self.classifier_model_name is not None:
            from transformers import pipeline
            self.classifier_model = pipeline("zero-shot-classification", model=classifier_model_name)

        if initialize_sentiment_model is not None:
            from transformers import pipeline
            self.sentiment_model = pipeline("sentiment-analysis")
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

    def _init_sentiment_model(self):
        if self.sentiment_model is not None:
            raise AttributeError("Classifier already initialized")

        from transformers import pipeline
        self.sentiment_model = pipeline("sentiment-analysis")

    def init_vader_sentiment_analyzer(self):
        if self.vader_sentiment_analyzer is not None:
            raise AttributeError("Classifier already initialized")

        from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
        self.vader_sentiment_analyzer = SentimentIntensityAnalyzer()

    def _get_sentiment_score(self, text: str, use_sentiment_model: bool = False) -> float:
        if use_sentiment_model:
            if self.sentiment_model is None:
                self._init_sentiment_model()

            score = self.sentiment_model(text)[0]

            return score['score'] if 'POSITIVE' == score['label'] else -score['score']
        else:
            if self.vader_sentiment_analyzer is None:
                self.init_vader_sentiment_analyzer()

            scores = self.vader_sentiment_analyzer.polarity_scores(text)
            return scores["compound"]

    def _classify_text(self, text: str, labels: List[str]) -> Dict[str, float]:
        if self.classifier_model is None:
            self._init_classifier_model(self.classifier_model_name)

        scores_data = self.classifier_model(text, labels, multi_class=self.multi_class_classification)

        score_dict = {label: score for label, score in zip(scores_data["labels"], scores_data["scores"])}
        return dict(sorted(score_dict.items(), key=lambda x: x[1], reverse=True))

    def analyze_input(
        self,
        source_response_list: List[SourceResponse],
        labels: List[str] = None,
        use_sentiment_model: bool = False,
    ) -> List[AnalyzerResponse]:

        analyzer_output: List[AnalyzerResponse] = []
        for source_response in source_response_list:
            sentiment_value = self._get_sentiment_score(source_response.text, use_sentiment_model)
            if sentiment_value < 0.0:
                sentiment_type = "NEGATIVE"
            else:
                sentiment_type = "POSITIVE"

            if labels is not None:
                classification_map = self._classify_text(source_response.text, labels)
            else:
                classification_map = None

            analyzer_output.append(
                AnalyzerResponse(
                    text=source_response.text,
                    meta_information=source_response.meta_information,
                    sentiment_value=sentiment_value,
                    sentiment_type=sentiment_type,
                    classification_map=classification_map
                )
            )

        return analyzer_output
