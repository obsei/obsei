import logging
from typing import List, Optional
import uuid

from pydantic import BaseModel

from obsei.payload import TextPayload
from obsei.preprocessor.base_preprocessor import (
    BaseTextPreprocessor,
    BaseTextProcessorConfig,
)

logger = logging.getLogger(__name__)


class TextSplitterPayload(BaseModel):
    phrase: str
    chunk_id: int
    chunk_length: int
    start_index: int
    end_index: int
    document_id: str
    text_length: int
    total_chunks: Optional[int]


class TextSplitterConfig(BaseTextProcessorConfig):
    max_split_length: int = 512
    split_stride: int = 0  # overlap length
    document_id_key: Optional[str]  # document_id in meta


class TextSplitter(BaseTextPreprocessor):
    def preprocess_input(  # type: ignore[override]
        self, input_list: List[TextPayload], config: TextSplitterConfig, **kwargs
    ) -> List[TextPayload]:
        text_splits: List[TextPayload] = []
        for idx, input_data in enumerate(input_list):
            if (
                config.document_id_key
                and input_data.meta
                and config.document_id_key in input_data.meta
            ):
                document_id = str(input_data.meta.get(config.document_id_key))
            else:
                document_id = uuid.uuid4().hex
            start_idx = 0
            split_id = 0
            document_splits: List[TextSplitterPayload] = []
            document_length = len(input_data.processed_text)
            while start_idx < document_length:
                if config.split_stride > 0 and start_idx > 0:
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
                    TextSplitterPayload(
                        phrase=phrase,
                        chunk_id=split_id,
                        chunk_length=len(phrase),
                        start_index=start_idx,
                        end_index=end_idx,
                        document_id=document_id,
                        text_length=document_length,
                    )
                )
                start_idx = end_idx + 1
                split_id += 1

            total_splits = len(document_splits)
            for split in document_splits:
                split.total_chunks = total_splits
                payload = TextPayload(
                    processed_text=split.phrase,
                    source_name=input_data.source_name,
                    segmented_data=input_data.segmented_data,
                    meta={**input_data.meta, **{"splitter": split}}
                    if input_data.meta
                    else {"splitter": split},
                )
                text_splits.append(payload)

        return text_splits

    @staticmethod
    def _valid_index(document: str, idx: int):
        if idx <= 0:
            return 0
        if idx >= len(document):
            return len(document)
        new_idx = idx
        while new_idx > 0:
            if document[new_idx] in [" ", "\n", "\t"]:
                break
            new_idx -= 1
        return new_idx
