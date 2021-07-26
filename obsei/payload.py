from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class BasePayload(BaseModel):
    segmented_data: Dict[str, Any] = Field({})
    meta: Dict[str, Any] = Field({})
    source_name: Optional[str] = "Undefined"

    class Config:
        arbitrary_types_allowed = True


class TextPayload(BasePayload):
    processed_text: str

    def to_dict(self):
        return {
            "processed_text": self.processed_text,
            "segmented_data": self.segmented_data,
            "meta": self.meta,
            "source_name": self.source_name,
        }

    def is_contains_classification_payload(self) -> bool:
        if self.segmented_data:
            if "classifier_data" in self.segmented_data:
                return True
        return False

    class Config:
        arbitrary_types_allowed = True
