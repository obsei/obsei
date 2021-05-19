from abc import abstractmethod
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, PrivateAttr

from obsei.misc import gpu_util
from obsei.workflow.base_store import BaseStore


class AnalyzerRequest(BaseModel):
    processed_text: str
    source_name: str = "Undefined"
    meta: Optional[Dict[str, Any]] = None


class AnalyzerResponse(BaseModel):
    processed_text: str
    segmented_data: Optional[Dict[str, Any]] = None
    meta: Optional[Dict[str, Any]] = None
    source_name: Optional[str] = None

    def to_dict(self):
        return {
            "processed_text": self.processed_text,
            "segmented_data": self.segmented_data,
            "meta": self.meta,
            "source_name": self.source_name,
        }


class BaseAnalyzerConfig(BaseModel):
    TYPE: str = "Base"

    class Config:
        arbitrary_types_allowed = True


class BaseAnalyzer(BaseModel):
    _device_id: int = PrivateAttr()
    TYPE: str = "Base"
    store: Optional[BaseStore] = None
    device: str = "auto"

    """
        auto: choose gpu if present else use cpu
        cpu: use cpu
        cuda:{id} - cuda device id
    """

    def __init__(self, **data: Any):
        super().__init__(**data)
        self._device_id = gpu_util.get_device_id(self.device)

    @abstractmethod
    def analyze_input(
        self,
        source_response_list: List[AnalyzerRequest],
        analyzer_config: BaseAnalyzerConfig,
        **kwargs
    ) -> List[AnalyzerResponse]:
        pass

    class Config:
        arbitrary_types_allowed = True
