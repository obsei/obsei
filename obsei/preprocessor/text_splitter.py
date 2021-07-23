import logging
from typing import Any, List, Optional
import uuid

from obsei.payload import TextPayload
from obsei.preprocessor.base_preprocessor import (
    BaseTextPreprocessor,
    BaseTextProcessorConfig,
)

logger = logging.getLogger(__name__)


class TextSplitterConfig(BaseTextProcessorConfig):
    max_split_length: int = 512
    split_stride: Optional[int] = 0  # overlap length
    generate_document_id: Optional[bool] = True

    def __init__(self, **data):
        super().__init__(**data)


class TextSplitter(BaseTextPreprocessor):
    def preprocess_input(
        self, input_list: List[TextPayload], config: TextSplitterConfig, **kwargs
    ) -> List[TextPayload]:
        splits = []
        document_id = 0
        for input_data in input_list:
            if config.generate_document_id:
                document_id = uuid.uuid4().int
            start_idx = 0
            split_id = 0
            document_splits = []
            document_length = len(input_data.processed_text)
            while start_idx < document_length:
                if config.split_stride and start_idx:
                    start_idx = (
                        self._valid_index(
                            input_data.processed_text, start_idx - config.split_stride
                        )
                        + 1
                    )
                end_idx = self._valid_index(
                    input_data.processed_text,
                    min(start_idx + config.max_split_length, document_length),
                )
                phrase = input_data.processed_text[start_idx:end_idx]
                document_splits.append(
                    (phrase, start_idx, split_id, document_id, document_length)
                )
                start_idx = end_idx + 1
                split_id += 1

            total_splits = len(document_splits)
            splits.extend(
                [self._build_payload(total_splits, *s) for s in document_splits]
            )

        return splits

    def _valid_index(self, document, end_id):
        if end_id <= 0 or end_id == len(document):
            return max(0, end_id)
        idx = end_id
        while idx > 0:
            if document[idx] in [" ", "\n", "\t"]:
                break
            idx -= 1
        return idx

    def _build_payload(
        self,
        total_splits,
        phrase,
        start_idx,
        split_id,
        document_id=0,
        document_length=0,
    ):
        return TextPayload(
            processed_text=phrase,
            segmented_data={"phrase": phrase},
            meta={
                "text": phrase,
                "chunk_id": split_id,
                "text_length": len(phrase),
                "start_index": start_idx,  # start position of split in document
                "document_id": document_id,
                "document_length": document_length,
                "total_splits": total_splits,
            },
        )
