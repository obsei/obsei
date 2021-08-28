import torch
from gensim.models.ldamodel import LdaModel
from typing import Any, Dict, List, Tuple
from obsei.payload import TextPayload

import umap.umap_ as umap
import numpy as np
from sklearn.feature_extraction.text import CountVectorizer
import pandas as pd
import hdbscan

import keras
from keras.layers import Input, Dense
from keras.models import Model
from sklearn.model_selection import train_test_split
import warnings

warnings.filterwarnings("ignore")


def get_umap_embedings(
    embeddings: List[torch.Tensor], n_neighbors: int, n_component: int
) -> np.ndarray:
    return umap.UMAP(
        n_neighbors=n_neighbors, n_components=n_component, metric="cosine"
    ).fit_transform(embeddings)


def cluster_embeddings(embeddings: np.ndarray, min_cluster_size: int) -> object:
    return hdbscan.HDBSCAN(
        min_cluster_size=min_cluster_size,
        metric="euclidean",
        cluster_selection_method="eom",
    ).fit(embeddings)


def get_topics_by_cluster(
    docs: List[str], cluster, source_input_list
) -> List[TextPayload]:
    docs_df = pd.DataFrame(docs, columns=["text"])
    docs_df["source_name"] = [
        source_input.source_name for source_input in source_input_list
    ]
    docs_df["topic"] = cluster.labels_
    docs_df["doc_id"] = range(len(docs_df))
    docs_per_topic = docs_df.groupby(["topic"], as_index=False)
    docs_per_topic_agg = docs_per_topic.agg({"text": " ".join})

    top_n_words_list = []
    tf_idf, count = c_tf_idf(docs_per_topic_agg.text.values, m=len(docs))
    top_n_words = extract_top_n_words_per_topic(
        tf_idf, count, docs_per_topic_agg, n=20
    )  # todo, can add to filter out stopwords
    topic_sizes = extract_topic_sizes(docs_df)

    top_k = 5
    top_n_words_dict = {}
    for c_no, value in top_n_words.items():
        if c_no == -1:
            top_n_words_dict[-1] = "~OUTLIERS~"
        cluster = sorted(value, key=lambda x: x[1])
        top_n_words_dict[c_no] = "_".join([i for i, j in cluster[-top_k:]])

    for name, group in docs_per_topic:

        payload = TextPayload(
            processed_text=top_n_words_dict[name],
            meta={
                "cluster_size": topic_sizes[name],
                "cluster_topics": top_n_words_dict[name],
            },
            segmented_data={
                "cluster_texts": [
                    TextPayload(
                        processed_text=t["text"],
                        meta={"cluster_id": name},
                        source_name=t["source_name"],
                    )
                    for j, t in group.iterrows()
                ]
            },
        )
        top_n_words_list.append(payload)

    return top_n_words_list


def c_tf_idf(documents, m, ngram_range=(1, 1)):
    count = CountVectorizer(ngram_range=ngram_range, stop_words="english").fit(
        documents
    )
    t = count.transform(documents).toarray()
    w = t.sum(axis=1)
    tf = np.divide(t.T, w)
    sum_t = t.sum(axis=0)
    idf = np.log(np.divide(m, sum_t)).reshape(-1, 1)
    tf_idf = np.multiply(tf, idf)

    return tf_idf, count


def extract_top_n_words_per_topic(
    tf_idf: np.ndarray, count: CountVectorizer, docs_per_topic: pd.DataFrame, n: int = 20
) -> Dict:
    words = count.get_feature_names()
    labels = list(docs_per_topic.topic)
    tf_idf_transposed = tf_idf.T
    indices = tf_idf_transposed.argsort()[:, -n:]
    top_n_words = {
        label: [(words[j], tf_idf_transposed[i][j]) for j in indices[i]][::-1]
        for i, label in enumerate(labels)
    }
    return top_n_words


def extract_topic_sizes(df):
    topic_sizes = (
        df.groupby(["topic"])
        .text.count()
        .reset_index()
        .rename({"topic": "topic", "text": "Size"}, axis="columns")
        .sort_values("Size", ascending=False)
    ).to_numpy()
    return {key: value for key, value in topic_sizes}


def get_vec_lda(model: LdaModel, corpus: List, k: int):
    """
    Get the LDA vector representation (probabilistic topic assignments for all documents)
    :return: vec_lda with dimension: (n_doc * n_topic)
    """
    n_doc = len(corpus)
    vec_lda = np.zeros((n_doc, k))
    for i in range(n_doc):
        # get the distribution for the i-th document in corpus
        for topic, prob in model.get_document_topics(corpus[i]):
            vec_lda[i, topic] = prob

    return vec_lda


class Autoencoder:
    """
    Autoencoder for learning latent space representation
    architecture simplified for only one hidden layer
    """

    def __init__(self, latent_dim=32, activation="relu", epochs=200, batch_size=128):
        self.latent_dim = latent_dim
        self.activation = activation
        self.epochs = epochs
        self.batch_size = batch_size
        self.autoencoder = None
        self.encoder = None
        self.decoder = None
        self.his = None

    def _compile(self, input_dim):
        """
        compile the computational graph
        """
        input_vec = Input(shape=(input_dim,))
        encoded = Dense(self.latent_dim, activation=self.activation)(input_vec)
        decoded = Dense(input_dim, activation=self.activation)(encoded)
        self.autoencoder = Model(input_vec, decoded)
        self.encoder = Model(input_vec, encoded)
        encoded_input = Input(shape=(self.latent_dim,))
        decoder_layer = self.autoencoder.layers[-1]
        self.decoder = Model(encoded_input, self.autoencoder.layers[-1](encoded_input))
        self.autoencoder.compile(optimizer="adam", loss=keras.losses.mean_squared_error)

    def fit(self, X):
        if not self.autoencoder:
            self._compile(X.shape[1])
        X_train, X_test = train_test_split(X)
        self.his = self.autoencoder.fit(
            X_train,
            X_train,
            epochs=self.epochs,
            batch_size=self.batch_size,
            shuffle=True,
            validation_data=(X_test, X_test),
            verbose=0,
        )
