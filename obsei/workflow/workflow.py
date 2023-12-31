from typing import Any, Dict, Optional
from uuid import uuid4

from pydantic import BaseModel, Field

from obsei.analyzer.base_analyzer import BaseAnalyzerConfig
from obsei.sink.base_sink import BaseSinkConfig
from obsei.source.base_source import BaseSourceConfig


class WorkflowConfig(BaseModel):
    source_config: Optional[BaseSourceConfig] = None
    sink_config: Optional[BaseSinkConfig] = None
    analyzer_config: Optional[BaseAnalyzerConfig] = None
    time_in_seconds: Optional[int] = None

    class Config:
        arbitrary_types_allowed = True


class WorkflowState(BaseModel):
    source_state: Optional[Dict[str, Any]] = None
    sink_state: Optional[Dict[str, Any]] = None
    analyzer_state: Optional[Dict[str, Any]] = None

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
