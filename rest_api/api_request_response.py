from typing import Dict, List

from pydantic.main import BaseModel

from obsei.analyzer.text_analyzer import AnalyzerConfig


class ClassifierRequest(BaseModel):
    texts: List[str]
    analyzer_config: AnalyzerConfig = AnalyzerConfig(use_sentiment_model=False)

    class Config:
        arbitrary_types_allowed = True


class ClassifierResponse(BaseModel):
    data: List[Dict[str, float]]


class ScheduleResponse(BaseModel):
    id: str
    run_frequency: str
    next_run: str

    class Config:
        arbitrary_types_allowed = True


class WorkflowAddResponse(BaseModel):
    id: str
