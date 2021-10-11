import logging
from typing import Any, List, Optional

import torch
from pydantic import PrivateAttr
from transformers import Pipeline
from gensim import corpora
from gensim.models.ldamodel import LdaModel

from obsei.analyzer.auto_encoder import AutoEncoder
from obsei.analyzer.base_analyzer import BaseAnalyzer, BaseAnalyzerConfig, MAX_LENGTH
from torch import Tensor
from obsei.payload import TextPayload
from obsei.analyzer.topic_analyzer_utils import (
    get_topics_by_cluster,
    get_umap_embeddings,
    cluster_embeddings,
    get_vec_lda,
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
    method: str = "LDA"


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
            "LDA_BERT": self._get_topic_lda_bert,
        }

    def analyze_input(
        self,
        source_response_list: List[TextPayload],
        analyzer_config: Optional[TopicAnalyzerConfig] = None,
        **kwargs,
    ) -> List[TextPayload]:
        if analyzer_config is None:
            raise ValueError("analyzer_config can't be None")
        analyzer_output = self.methods[analyzer_config.method](source_response_list)
        return analyzer_output

    def _get_topic_bert(
        self,
        source_response_list: List[TextPayload],
        umap_n_neighbors: int = 10,
        umap_n_components: int = 5,
        min_cluster_size: int = 5,
    ) -> List[TextPayload]:
        docs = [
            source_response.processed_text[: self._max_length]
            for source_response in source_response_list
        ]
        embeddings = self._get_transformer_embeddings(docs)
        umap_embeddings = get_umap_embeddings(
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
        topics = lda_model.show_topics(formatted=False, num_topics=1)
        topics_list = [topic_tuple[1][1] for topic_tuple in topics]
        topics_list = [topic[0] for topic in topics_list]
        analyzer_output = [
            TextPayload(
                processed_text="_".join(topics_list),
                meta={"cluster_topics": topics_list},
            )
        ]
        return analyzer_output

    def _get_lda_embeddings(
        self, source_input_list: List[TextPayload], num_topics: int = 10
    ):
        token_lists = self._prepare_tokens(source_input_list)
        dictionary = corpora.Dictionary(token_lists)
        corpus = [dictionary.doc2bow(text) for text in token_lists]
        lda_model = LdaModel(
            corpus, num_topics=num_topics, id2word=dictionary, passes=5
        )
        embeddings = get_vec_lda(lda_model, corpus, num_topics)
        return embeddings, lda_model

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

    def _get_topic_lda_bert(
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
        embeddings_lda_bert = np.c_[embeddings_lda * gamma, embeddings_bert].astype(np.float32)
        auto_encoder = AutoEncoder(input_dim=embeddings_lda_bert.shape[1])
        auto_encoder.train_model(embeddings_lda_bert)
        lda_bert_embeddings = auto_encoder.predict_encoder(torch.from_numpy(embeddings_lda_bert))
        umap_embeddings = get_umap_embeddings(
            embeddings=lda_bert_embeddings,
            n_neighbors=umap_n_neighbors,
            n_component=umap_n_components,
        )
        clusters = cluster_embeddings(
            umap_embeddings, min_cluster_size=min_cluster_size
        )
        topics_per_cluster = get_topics_by_cluster(docs, clusters, source_input_list)
        return topics_per_cluster
