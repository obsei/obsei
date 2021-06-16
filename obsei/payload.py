from typing import Any, Dict, Optional

from pydantic import BaseModel


class BasePayload(BaseModel):
    segmented_data: Optional[Dict[str, Any]] = None
    meta: Optional[Dict[str, Any]] = None
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

    class Config:
        arbitrary_types_allowed = True
