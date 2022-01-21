from abc import abstractmethod
from typing import Any, Generator, List, Optional

from pydantic import BaseSettings, Field, PrivateAttr

from obsei.misc import gpu_util
from obsei.payload import TextPayload
from obsei.postprocessor.inference_aggregator import (
    InferenceAggregator,
    InferenceAggregatorConfig,
)
from obsei.preprocessor.text_splitter import TextSplitter, TextSplitterConfig
from obsei.workflow.base_store import BaseStore

MAX_LENGTH: int = 510
DEFAULT_BATCH_SIZE_GPU: int = 64
DEFAULT_BATCH_SIZE_CPU: int = 4


class BaseAnalyzerConfig(BaseSettings):
    TYPE: str = "Base"
    use_splitter_and_aggregator: Optional[bool] = False
    splitter_config: Optional[TextSplitterConfig]
    aggregator_config: Optional[InferenceAggregatorConfig]

    def __init__(self, **data: Any):
        super().__init__(**data)

        if self.use_splitter_and_aggregator and not self.splitter_config and not self.aggregator_config:
            raise AttributeError("Need splitter_config and aggregator_config if enabling use_splitter_and_aggregator "
                                 "option")

    class Config:
        arbitrary_types_allowed = True


class BaseAnalyzer(BaseSettings):
    _device_id: int = PrivateAttr()
    TYPE: str = "Base"
    store: Optional[BaseStore] = None
    device: str = "auto"
    batch_size: int = -1
    splitter: TextSplitter = Field(TextSplitter())
    aggregator: InferenceAggregator = Field(InferenceAggregator())

    """
        auto: choose gpu if present else use cpu
        cpu: use cpu
        cuda:{id} - cuda device id
    """

    def __init__(self, **data: Any):
        super().__init__(**data)

        self._device_id = gpu_util.get_device_id(self.device)
        if self.batch_size < 0:
            self.batch_size = (
                DEFAULT_BATCH_SIZE_CPU
                if self._device_id == 0
                else DEFAULT_BATCH_SIZE_GPU
            )

    @abstractmethod
    def analyze_input(
        self,
        source_response_list: List[TextPayload],
        analyzer_config: Optional[BaseAnalyzerConfig] = None,
        **kwargs,
    ) -> List[TextPayload]:
        pass

    @staticmethod
    def batchify(
        payload_list: List[TextPayload],
        batch_size: int,
    ) -> Generator[List[TextPayload], None, None]:
        for index in range(0, len(payload_list), batch_size):
            yield payload_list[index : index + batch_size]

    class Config:
        arbitrary_types_allowed = True
