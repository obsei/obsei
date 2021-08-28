import logging
from typing import Any, List, Optional

from pydantic import Field, PrivateAttr
from transformers import Pipeline
from gensim import corpora
from gensim.models.ldamodel import LdaModel
from obsei.analyzer.base_analyzer import BaseAnalyzer, BaseAnalyzerConfig, MAX_LENGTH
from torch import Tensor
import re
from obsei.payload import TextPayload
from obsei.postprocessor.inference_aggregator import InferenceAggregatorConfig
from obsei.postprocessor.inference_aggregator_function import ClassificationAverageScore
from obsei.analyzer.topic_analyzer_utils import (
    get_topics_by_cluster,
    get_umap_embedings,
    cluster_embeddings,
    get_vec_lda,
    Autoencoder,
)
from sentence_transformers import SentenceTransformer
from obsei.preprocessor.text_cleaner import TextCleanerConfig, TextCleaner
from obsei.preprocessor.text_tokenizer import NLTKTextTokenizer
from obsei.preprocessor.text_cleaning_function import (
    RemovePunctuation,
    RemoveStopWords,
    RemoveWhiteSpaceAndEmptyToken,
    ToLowerCase,
)
import numpy as np

logger = logging.getLogger(__name__)


class TopicAnalyzerConfig(BaseAnalyzerConfig):
    TYPE: str = "TopicModelling"
    labels: List[str]
    multi_class_classification: bool = True
    aggregator_config: InferenceAggregatorConfig = Field(
        InferenceAggregatorConfig(aggregate_function=ClassificationAverageScore())
    )


class TopicClassificationAnalyzer(BaseAnalyzer):
    _pipeline: Pipeline = PrivateAttr()
    _max_length: int = PrivateAttr()
    TYPE: str = "TopicModelling"
    model_name_or_path: str
    methods: dict = {}

    def __init__(self, **data: Any):
        super().__init__(**data)
        self._max_length = MAX_LENGTH
        self.methods = {
            "BERT": self._get_topic_bert,
            "LDA": self._get_topic_lda,
            "LDA_BERT": self._get_topic_ldabert,
        }

    def analyze_input(
        self,
        source_response_list: List[TextPayload],
        analyzer_config: Optional[TopicAnalyzerConfig] = None,
        **kwargs,
    ) -> List[TextPayload]:
        if analyzer_config is None:
            raise ValueError("analyzer_config can't be None")
        analyzer_output = []
        for label in analyzer_config.labels:
            if label not in self.methods.keys():
                label = "LDA"
            analyzer_output.append(self.methods[label](source_response_list))
        return analyzer_output

    def _get_topic_bert(
        self,
        source_response_list: List[TextPayload],
        umap_n_neighbors: int = 10,
        umap_n_components: int = 5,
        min_cluster_size: int = 10,
    ) -> List[TextPayload]:
        docs = [
            source_response.processed_text[: self._max_length]
            for source_response in source_response_list
        ]
        embeddings = self._get_transformer_embeddings(docs)
        umap_embeddings = get_umap_embedings(
            embeddings=embeddings,
            n_neighbors=umap_n_neighbors,
            n_component=umap_n_components,
        )
        clusters = cluster_embeddings(
            umap_embeddings, min_cluster_size=min_cluster_size
        )
        topics_per_cluster = get_topics_by_cluster(docs, clusters, source_response_list)
        return topics_per_cluster

    def _get_transformer_embeddings(self, docs: List[str]) -> List[Tensor]:
        model = SentenceTransformer(self.model_name_or_path)
        embeddings = model.encode(docs, show_progress_bar=True)
        return embeddings

    def _get_topic_lda(self, source_input_list: List[TextPayload]):
        _, lda_model = self._get_lda_embeddings(source_input_list)
        topics = lda_model.show_topics()
        topics_list = [re.findall(r'"([^"]*)"', t[1]) for t in topics]
        analyzer_output = [
            TextPayload(
                processed_text="_".join(t),
                meta={"cluster_topics": t},
            )
            for t in topics_list
        ]
        return analyzer_output

    def _get_lda_embeddings(
        self, source_input_list: List[TextPayload], num_topics: int = 10
    ):
        token_lists = self._prepare_tokens(source_input_list)
        dictionary = corpora.Dictionary(token_lists)
        corpus = [dictionary.doc2bow(text) for text in token_lists]
        ldamodel = LdaModel(
            corpus, num_topics=num_topics, id2word=dictionary, passes=20
        )
        embeddings = get_vec_lda(ldamodel, corpus, num_topics)
        return embeddings, ldamodel

    def _prepare_tokens(self, source_response_list: List[TextPayload]):
        tokenizer = NLTKTextTokenizer()
        preprocess_config = TextCleanerConfig(
            cleaning_functions=[
                RemoveWhiteSpaceAndEmptyToken(),
                RemovePunctuation(),
                RemoveStopWords(),
                ToLowerCase(),
            ]
        )  # Stemming
        preprocessor = TextCleaner()
        cleaner_responses = preprocessor.preprocess_input(
            config=preprocess_config, input_list=source_response_list
        )
        tokenized_texts = [
            tokenizer.tokenize_text(t.processed_text) for t in cleaner_responses
        ]
        return tokenized_texts

    def _get_topic_ldabert(
        self,
        source_input_list: List[TextPayload],
        umap_n_neighbors: int = 10,
        umap_n_components: int = 5,
        min_cluster_size: int = 10,
    ):
        gamma = 15  # modelparameter , importance of lda
        docs = [
            source_response.processed_text[: self._max_length]
            for source_response in source_input_list
        ]
        embeddings_bert = self._get_transformer_embeddings(docs)
        embeddings_lda, _ = self._get_lda_embeddings(source_input_list)
        embeddings_ldabert = np.c_[embeddings_lda * gamma, embeddings_bert]
        auto_encoder = Autoencoder()
        auto_encoder.fit(embeddings_ldabert)
        ldabert_embeddings = auto_encoder.encoder.predict(embeddings_ldabert)
        umap_embeddings = get_umap_embedings(
            embeddings=ldabert_embeddings,
            n_neighbors=umap_n_neighbors,
            n_component=umap_n_components,
        )
        clusters = cluster_embeddings(
            umap_embeddings, min_cluster_size=min_cluster_size
        )
        topics_per_cluster = get_topics_by_cluster(docs, clusters, source_input_list)
        return topics_per_cluster
