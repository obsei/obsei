from typing import Any, Dict, Optional
from uuid import uuid4

from pydantic import BaseModel

from obsei.analyzer.text_analyzer import AnalyzerConfig
from obsei.sink.base_sink import BaseSinkConfig
from obsei.source.base_source import BaseSourceConfig


class WorkflowConfig(BaseModel):
    source_config: Optional[BaseSourceConfig]
    sink_config: Optional[BaseSinkConfig]
    analyzer_config: Optional[AnalyzerConfig]
    time_in_seconds: Optional[int]

    def __init__(self, **data: Any):
        super().__init__(**data)
        self.analyzer_config = self.analyzer_config or AnalyzerConfig(use_sentiment_model=False)

    class Config:
        arbitrary_types_allowed = True


class WorkflowState(BaseModel):
    source_state: Optional[Dict[str, Any]]
    sink_state: Optional[Dict[str, Any]]
    analyzer_state: Optional[Dict[str, Any]]

    class Config:
        arbitrary_types_allowed = True
        response_model_exclude_unset = True


class Workflow(BaseModel):
    id: str = str(uuid4())
    config: WorkflowConfig
    states: Optional[WorkflowState]

    def __init__(self, **data: Any):
        super().__init__(**data)
        self.states = self.states or WorkflowState()

    class Config:
        arbitrary_types_allowed = True
        response_model_exclude_unset = True
