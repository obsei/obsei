from typing import Any, List, Optional

from pydantic import PrivateAttr
from transformers import pipeline, Pipeline, AutoTokenizer, AutoModelForSeq2SeqLM

from obsei.analyzer.base_analyzer import (
    BaseAnalyzer,
    BaseAnalyzerConfig,
    MAX_LENGTH,
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
            self._max_length = MAX_LENGTH

    def analyze_input(
        self,
        source_response_list: List[TextPayload],
        analyzer_config: Optional[BaseAnalyzerConfig] = None,
        **kwargs,
    ) -> List[TextPayload]:

        analyzer_output = []

        for batch_responses in self.batchify(source_response_list, self.batch_size):
            texts = [
                source_response.processed_text[: self._max_length]
                for source_response in batch_responses
            ]

            batch_predictions = self._pipeline(texts)

            for prediction, source_response in zip(batch_predictions, batch_responses):
                segmented_data = {
                    "translation_data": {
                        "original_text": source_response.processed_text
                    }
                }
                if source_response.segmented_data:
                    segmented_data = {
                        **segmented_data,
                        **source_response.segmented_data,
                    }

                analyzer_output.append(
                    TextPayload(
                        processed_text=prediction["translation_text"],
                        meta=source_response.meta,
                        segmented_data=segmented_data,
                        source_name=source_response.source_name,
                    )
                )

        return analyzer_output
