from typing import Annotated, Any
from bson import ObjectId
from pydantic import BaseModel
from api.src.schema.listening_config import (
    Analyzer,
    AnalyzerConfig,
    Source,
    SourceConfig,
    Sink,
    SinkConfig,
)
from api.src.interfaces.pydantic_annotation import ObjectIdPydanticAnnotation


class StoreListeningConfigInputData(BaseModel):
    source: Source
    source_config: SourceConfig
    analyzer: Analyzer
    analyzer_config: AnalyzerConfig
    sink: Sink
    sink_config: SinkConfig
    user_id: str


class UpdateListeningConfigInputData(BaseModel):
    source: Source
    source_config: SourceConfig
    analyzer: Analyzer
    analyzer_config: AnalyzerConfig
    sink: Sink
    sink_config: SinkConfig


class StoreListeningConfigOutData(BaseModel):
    id: Annotated[ObjectId, ObjectIdPydanticAnnotation]


class GetListeningConfigOutData(BaseModel):
    id: Annotated[ObjectId, ObjectIdPydanticAnnotation]
    source: object
    source_config: object
    analyzer: object
    analyzer_config: object
    sink: object
    sink_config: object
    user_id: str
