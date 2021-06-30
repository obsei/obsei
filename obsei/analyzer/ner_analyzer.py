import logging
from typing import Any, Dict, List, Tuple, Optional, Generator

from pydantic import PrivateAttr
from transformers import (
    AutoModelForTokenClassification,
    AutoTokenizer,
    Pipeline,
    pipeline,
)

from obsei.analyzer.base_analyzer import (
    BaseAnalyzer,
    BaseAnalyzerConfig,
)
from obsei.payload import TextPayload

logger = logging.getLogger(__name__)


class NERAnalyzer(BaseAnalyzer):
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
            self._max_length = 510

    def _classify_text_from_model(
        self, texts: List[str]
    ) -> List[List[Dict[str, float]]]:
        prediction = self._pipeline(texts)
        return (
            prediction
            if len(prediction) and isinstance(prediction[0], list)
            else [prediction]
        )

    def _batchify(
        self,
        texts: List[str],
        batch_size: int,
        source_response_list: List[TextPayload],
    ) -> Generator[Tuple[List[str], List[TextPayload]], None, None]:
        for index in range(0, len(texts), batch_size):
            yield (
                texts[index : index + batch_size],
                source_response_list[index : index + batch_size],
            )

    def analyze_input(
        self,
        source_response_list: List[TextPayload],
        analyzer_config: Optional[BaseAnalyzerConfig] = None,
        **kwargs,
    ) -> List[TextPayload]:
        analyzer_output: List[TextPayload] = []
        texts = [
            source_response.processed_text[: self._max_length]
            if len(source_response.processed_text) > self._max_length
            else source_response.processed_text
            for source_response in source_response_list
        ]

        for batch_texts, batch_source_response in self._batchify(
            texts, self.batch_size, source_response_list
        ):
            batch_ner_predictions = self._classify_text_from_model(batch_texts)
            for ner_prediction, source_response in zip(
                batch_ner_predictions, batch_source_response
            ):
                analyzer_output.append(
                    TextPayload(
                        processed_text=source_response.processed_text,
                        meta=source_response.meta,
                        segmented_data={"data": ner_prediction},
                        source_name=source_response.source_name,
                    )
                )
        return analyzer_output
