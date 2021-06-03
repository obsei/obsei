from typing import Any, Dict, Optional
from uuid import uuid4

from pydantic import BaseModel, Field

from obsei.analyzer.base_analyzer import BaseAnalyzerConfig
from obsei.sink.base_sink import BaseSinkConfig
from obsei.source.base_source import BaseSourceConfig


class WorkflowConfig(BaseModel):
    source_config: Optional[BaseSourceConfig]
    sink_config: Optional[BaseSinkConfig]
    analyzer_config: Optional[BaseAnalyzerConfig]
    time_in_seconds: Optional[int]

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
    states: WorkflowState = Field(WorkflowState())

    class Config:
        arbitrary_types_allowed = True
        response_model_exclude_unset = True
