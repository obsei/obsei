from typing import List, Any
from typing import Any, Dict, List, Tuple, Optional, Generator

from pydantic import PrivateAttr
from transformers import pipeline, Pipeline, AutoTokenizer, AutoModelForSeq2SeqLM

from obsei.analyzer.base_analyzer import (
    BaseAnalyzer,
    BaseAnalyzerConfig,
)
from obsei.payload import TextPayload


class TranslationAnalyzer(BaseAnalyzer):
    _pipeline: Pipeline = PrivateAttr()
    _max_length: int = PrivateAttr()
    TYPE: str = "Translation"
    model_name_or_path: str

    def __init__(self, **data: Any):
        super().__init__(**data)
        tokenizer = AutoTokenizer.from_pretrained(self.model_name_or_path)
        model = AutoModelForSeq2SeqLM.from_pretrained(self.model_name_or_path)
        self._pipeline = pipeline(
            "translation", model=model, tokenizer=tokenizer, device=self._device_id
        )
        if hasattr(self._pipeline.model.config, "max_position_embeddings"):
            self._max_length = self._pipeline.model.config.max_position_embeddings
        else:
            self._max_length = 510

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

        analyzer_output = []
        texts = [
            source_response.processed_text[: self._max_length]
            if len(source_response.processed_text) > self._max_length
            else source_response.processed_text
            for source_response in source_response_list
        ]

        for batch_texts, batch_source_response in self._batchify(
            texts, self.batch_size, source_response_list
        ):
            batch_predictions = self._pipeline(batch_texts)

            for prediction, source_response in zip(
                batch_predictions, batch_source_response
            ):

                analyzer_output.append(
                    TextPayload(
                        processed_text=source_response.processed_text,
                        meta=source_response.meta,
                        segmented_data={
                            "translated_text": prediction["translation_text"]
                        },
                        source_name=source_response.source_name,
                    )
                )

        return analyzer_output
