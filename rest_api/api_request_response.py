import json
from abc import ABC
from typing import Any, Dict, List, Optional

from pydantic.main import BaseModel

from obsei.sink.sink_utils import sink_config_from_dict
from obsei.source.source_utils import source_config_from_dict


class ClassifierRequest(BaseModel):
    texts: List[str]
    labels: List[str]
    use_sentiment_model: bool = True

    class Config:
        arbitrary_types_allowed = True


class ClassifierResponse(BaseModel):
    data: List[Dict[str, float]]


class SinkConfig(BaseModel):
    name: str
    config: Dict[str, Any]


class SourceConfig(BaseModel):
    name: str
    config: Dict[str, Any]


class TaskConfig(BaseModel):
    sink_config: SinkConfig
    source_config: SourceConfig
    time_in_seconds: int

    def to_json(self):
        return json.dumps(self, default=lambda o: o.__dict__, sort_keys=True, indent=4)


class TaskConfigObjects(ABC):
    def __init__(self, config: TaskConfig):
        self.sink, self.sink_config = sink_config_from_dict(
            config.sink_config.name,
            config.sink_config.config
        )
        self.source, self.source_config = source_config_from_dict(
            config.source_config.name,
            config.source_config.config
        )


class ScheduleResponse(BaseModel):
    id: str
    run_frequency: str
    next_run: str


class TaskDetail(BaseModel):
    id: Optional[str]
    config: TaskConfig

