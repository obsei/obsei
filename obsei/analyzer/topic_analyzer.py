import logging
from typing import Any, Dict, List, Optional

from pydantic import Field, PrivateAttr
from transformers import Pipeline, pipeline

from obsei.analyzer.base_analyzer import (
    BaseAnalyzer,
    BaseAnalyzerConfig,
    MAX_LENGTH
)
from obsei.payload import TextPayload
from obsei.postprocessor.inference_aggregator import InferenceAggregatorConfig
from obsei.postprocessor.inference_aggregator_function import ClassificationAverageScore
from obsei.analyzer.topic_analyzer_utils import get_topics_by_cluster, get_umap_embedings, cluster_embeddings
from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)


class TopicAnalyzerConfig(BaseAnalyzerConfig):
    TYPE: str = "TopicModelling"
    labels: List[str]
    multi_class_classification: bool = True
    aggregator_config: InferenceAggregatorConfig = Field(
        InferenceAggregatorConfig(
            aggregate_function=ClassificationAverageScore()
        )
    )

class TopicClassificationAnalyzer(BaseAnalyzer):
    _pipeline: Pipeline = PrivateAttr()
    _max_length: int = PrivateAttr()
    TYPE: str = "TopicModelling"
    model_name_or_path: str
    method : str

    def __init__(self, **data: Any):
        super().__init__(**data)
        self._max_length = MAX_LENGTH

    def _get_topics(self, docs, source_name):
        if self.method == "BERT":
            return self._get_topic_bert(docs, source_name)
        if self.method == "LDA":
            return self._get_topic_lda(docs)
        elif self.method == "LDA_BERT":
            return self.get_topics_ldabert(docs)

        return None

    def _get_topic_bert(self, docs, source_name,  umap_n_neighbors = 10, umap_n_components = 5, min_cluster_size = 10):
        embeddings = self._get_transformer_embeddings()
        umap_embeddings = get_umap_embedings(embeddings = embeddings, n_neighbors= umap_n_neighbors, n_component= umap_n_components)
        clusters = cluster_embeddings(umap_embeddings, min_cluster_size = min_cluster_size)
        topics_per_cluster = get_topics_by_cluster(docs, clusters, source_name)
        return topics_per_cluster

    def _get_transformer_embeddings(self):
        model = SentenceTransformer(self.model_name_or_path)
        embeddings = model.encode(docs, show_progress_bar=True)
        return embeddings

    def analyze_input(
        self,
        source_response_list: List[TextPayload],
        analyzer_config: Optional[BaseAnalyzerConfig] = None,
        **kwargs,
    ) -> List[TextPayload]:
        # if analyzer_config is None:
        #     raise ValueError("analyzer_config can't be None")
        source_name = source_response_list[0].source_name
        analyzer_output: List[TextPayload] = []
        texts = [
            source_response.processed_text[: self._max_length]
            for source_response in source_response_list
        ]

        analyzer_output = self._get_topics(texts,source_name) # other params in config?

        return  analyzer_output# maybe return list of text payload only , with processed text as the discoverd topic names,
    # and meta contains all the texts / list of payloads contained in that Payload

# if __name__ == '__main__':
#     from obsei.source.playstore_scrapper import PlayStoreScrapperConfig, PlayStoreScrapperSource
#
#     # initialize play store source config
#     source_config = PlayStoreScrapperConfig(
#         # Need two parameters package_name and country.
#         # `package_name` can be found at the end of the url of app in play store.
#         # For example - https://play.google.com/store/apps/details?id=com.google.android.gm&hl=en&gl=US
#         # `com.google.android.gm` is the package_name for xcode and `us` is country.
#         countries=["in"],
#         package_name="tv.twitch.android.app",
#         lookup_period="1h"  # Lookup period from current time, format: `<number><d|h|m>` (day|hour|minute)
#     )
#
#     # initialize play store reviews retriever
#     source = PlayStoreScrapperSource()
#     source_list = source.lookup(source_config)
#     docs = [s.processed_text for s in source_list]
#     topic_analyzer = TopicClassificationAnalyzer(model_name_or_path = "paraphrase-distilroberta-base-v2",method = "BERT")
#     clusters = topic_analyzer.analyze_input(source_list)
#     x = 1
#
#
