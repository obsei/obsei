from typing import List, Any

from pydantic import PrivateAttr
from transformers import pipeline, Pipeline, AutoTokenizer, AutoModelForSeq2SeqLM

from obsei.analyzer.base_analyzer import AnalyzerRequest, AnalyzerResponse, BaseAnalyzer


class TranslationAnalyzer(BaseAnalyzer):
    _pipeline: Pipeline = PrivateAttr()
    TYPE: str = "Translation"
    model_name_or_path: str

    def __init__(self, **data: Any):
        super().__init__(**data)
        tokenizer = AutoTokenizer.from_pretrained(self.model_name_or_path)
        model = AutoModelForSeq2SeqLM.from_pretrained(self.model_name_or_path)
        self._pipeline = pipeline(
            "translation", model=model, tokenizer=tokenizer, device=self._device_id
        )

    def analyze_input(
        self, source_response_list: List[AnalyzerRequest], **kwargs
    ) -> List[AnalyzerResponse]:
        responses = []
        for source_response in source_response_list:
            translated_text = self._pipeline(source_response.processed_text)
            responses.append(
                AnalyzerResponse(
                    processed_text=source_response.processed_text,
                    meta=source_response.meta,
                    source_name=source_response.source_name,
                    segmented_data={
                        "translated_text": translated_text[0]["translation_text"]
                    },
                )
            )

        return responses
