from pydantic import BaseModel
from typing import List, Optional


class Analyzer(BaseModel):
    target__: str
    model_name_or_path: str
    device: Optional[str]


class AnalyzerConfig(BaseModel):
    target__: str
    labels: Optional[list]
    multi_class_classification: bool


class Source(BaseModel):
    target__: str


class SourceConfig(BaseModel):
    target__: str
    keywords: Optional[list]
    video_url: Optional[list]
    lookup_period: str
    max_comments: int
    max_search_video: int


class Sink(BaseModel):
    target__: str


class SinkConfig(BaseModel):
    target__: str


class CreateListeningConfigRequestBody(BaseModel):
    source: Source
    source_config: SourceConfig
    analyzer: Analyzer
    analyzer_config: AnalyzerConfig
    sink: Sink
    sink_config: SinkConfig
    user_id: str


class UpdateListeningConfigRequestBody(BaseModel):
    source: Source
    source_config: SourceConfig
    analyzer: Analyzer
    analyzer_config: AnalyzerConfig
    sink: Sink
    sink_config: SinkConfig
