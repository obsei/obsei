#  Copyright (c) 2020. Lalit Kumar Pagaria.
#
#  This program is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program.  If not, see <https://www.gnu.org/licenses/

from typing import Dict, List, Optional


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

    def init_classifier_model(self, classifier_model_name: str):
        if self.classifier_model is not None:
            raise AttributeError("Classifier already initialized")

        from transformers import pipeline
        self.classifier_model = pipeline("zero-shot-classification", model=classifier_model_name)

    def init_sentiment_model(self):
        if self.sentiment_model is not None:
            raise AttributeError("Classifier already initialized")

        from transformers import pipeline
        self.sentiment_model = pipeline("sentiment-analysis")

    def init_vader_sentiment_analyzer(self):
        if self.vader_sentiment_analyzer is not None:
            raise AttributeError("Classifier already initialized")

        from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
        self.vader_sentiment_analyzer = SentimentIntensityAnalyzer()

    def get_sentiment_score(self, text: str, use_model: bool = False) -> float:
        if use_model:
            if self.sentiment_model is None:
                self.init_sentiment_model()

            score = self.sentiment_model(text)[0]

            return score['score'] if 'POSITIVE' == score['label'] else -score['score']
        else:
            if self.vader_sentiment_analyzer is None:
                self.init_vader_sentiment_analyzer()

            scores = self.vader_sentiment_analyzer.polarity_scores(text)
            return scores["compound"]

    def classify_text(self, text: str, labels: List[str]) -> Dict[str, float]:
        if self.classifier_model is None:
            self.init_classifier_model(self.classifier_model_name)

        scores_data = self.classifier_model(text, labels, multi_class=self.multi_class_classification)

        score_dict = {label: score for label, score in zip(scores_data["labels"], scores_data["scores"])}
        return dict(sorted(score_dict.items(), key=lambda x: x[1], reverse=True))
