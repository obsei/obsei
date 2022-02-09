import logging
from typing import Any, Dict, Generator, List, Optional, Tuple, Iterator
from pydantic import PrivateAttr
from transformers import (
    AutoModelForTokenClassification,
    AutoTokenizer,
    Pipeline,
    pipeline,
)
import spacy
from spacy.language import Language
from spacy.tokens.doc import Doc
from obsei.analyzer.base_analyzer import (
    BaseAnalyzer,
    BaseAnalyzerConfig,
    MAX_LENGTH,
)
from obsei.payload import TextPayload

logger = logging.getLogger(__name__)


class TransformersNERAnalyzer(BaseAnalyzer):
    _pipeline: Pipeline = PrivateAttr()
    _max_length: int = PrivateAttr()
    TYPE: str = "NER"
    model_name_or_path: str
    tokenizer_name: Optional[str] = None
    grouped_entities: Optional[bool] = True

    def __init__(self, **data: Any):
        super().__init__(**data)

        model = AutoModelForTokenClassification.from_pretrained(self.model_name_or_path)
        tokenizer = AutoTokenizer.from_pretrained(
            self.tokenizer_name if self.tokenizer_name else self.model_name_or_path,
            use_fast=True,
        )

        self._pipeline = pipeline(
            "ner",
            model=model,
            tokenizer=tokenizer,
            grouped_entities=self.grouped_entities,
            device=self._device_id,
        )

        if hasattr(self._pipeline.model.config, "max_position_embeddings"):
            self._max_length = self._pipeline.model.config.max_position_embeddings
        else:
            self._max_length = MAX_LENGTH

    def _prediction_from_model(self, texts: List[str]) -> List[List[Dict[str, float]]]:
        prediction = self._pipeline(texts)
        return (
            prediction
            if len(prediction) and isinstance(prediction[0], list)
            else [prediction]
        )

    def analyze_input(
        self,
        source_response_list: List[TextPayload],
        analyzer_config: Optional[BaseAnalyzerConfig] = None,
        **kwargs,
    ) -> List[TextPayload]:
        analyzer_output: List[TextPayload] = []

        for batch_responses in self.batchify(source_response_list, self.batch_size):
            texts = [
                source_response.processed_text[: self._max_length]
                for source_response in batch_responses
            ]
            batch_predictions = self._prediction_from_model(texts)

            for prediction, source_response in zip(batch_predictions, batch_responses):
                segmented_data = {"ner_data": prediction}
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


class SpacyNERAnalyzer(BaseAnalyzer):
    _nlp: Language = PrivateAttr()
    TYPE: str = "NER"
    model_name_or_path: str
    tokenizer_name: Optional[str] = None
    grouped_entities: Optional[bool] = True
    n_process: int = 1

    def __init__(self, **data: Any):
        super().__init__(**data)
        self._nlp = spacy.load(
            self.model_name_or_path,
            disable=["tagger", "parser", "attribute_ruler", "lemmatizer"],
        )

    def _spacy_pipe_batchify(
        self,
        texts: List[str],
        batch_size: int,
        source_response_list: List[TextPayload],
    ) -> Generator[Tuple[Iterator[Doc], List[TextPayload]], None, None]:
        for index in range(0, len(texts), batch_size):
            yield (
                self._nlp.pipe(
                    texts=texts[index: index + batch_size],
                    batch_size=batch_size,
                    n_process=self.n_process,
                ),
                source_response_list[index: index + batch_size],
            )

    def analyze_input(
        self,
        source_response_list: List[TextPayload],
        analyzer_config: Optional[BaseAnalyzerConfig] = None,
        **kwargs,
    ) -> List[TextPayload]:
        analyzer_output: List[TextPayload] = []
        texts = [
            source_response.processed_text for source_response in source_response_list
        ]

        for batch_docs, batch_source_response in self._spacy_pipe_batchify(
            texts, self.batch_size, source_response_list
        ):
            for doc, source_response in zip(batch_docs, batch_source_response):
                ner_prediction = [
                    {
                        "entity_group": ent.label_,
                        "word": ent.text,
                        "start": ent.start_char,
                        "end": ent.end_char,
                    }
                    for ent in doc.ents
                ]
                segmented_data = {"ner_data": ner_prediction}
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
