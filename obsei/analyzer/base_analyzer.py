from abc import abstractmethod
from typing import Any, List, Optional

from pydantic import BaseModel, PrivateAttr

from obsei.misc import gpu_util
from obsei.payload import TextPayload
from obsei.workflow.base_store import BaseStore


class BaseAnalyzerConfig(BaseModel):
    TYPE: str = "Base"

    class Config:
        arbitrary_types_allowed = True


class BaseAnalyzer(BaseModel):
    _device_id: int = PrivateAttr()
    TYPE: str = "Base"
    store: Optional[BaseStore] = None
    device: str = "auto"
    batch_size: int = 64

    """
        auto: choose gpu if present else use cpu
        cpu: use cpu
        cuda:{id} - cuda device id
    """

    def __init__(self, **data: Any):
        super().__init__(**data)
        self._device_id = gpu_util.get_device_id(self.device)
        self.batch_size = 4 if self._device_id == 0 else self.batch_size

    @abstractmethod
    def analyze_input(
        self,
        source_response_list: List[TextPayload],
        analyzer_config: Optional[BaseAnalyzerConfig] = None,
        **kwargs,
    ) -> List[TextPayload]:
        pass

    class Config:
        arbitrary_types_allowed = True
