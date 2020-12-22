import json
from typing import Dict, List, Optional, Union

from pydantic.main import BaseModel

from obsei.sink.dailyget_sink import DailyGetSinkConfig
from obsei.sink.elasticsearch_sink import ElasticSearchSinkConfig
from obsei.sink.http_sink import HttpSinkConfig
from obsei.sink.jira_sink import JiraSinkConfig
from obsei.source.twitter_source import TwitterCredentials, TwitterSourceConfig
from obsei.analyzer.text_analyzer import AnalyzerConfig


class ClassifierRequest(BaseModel):
    texts: List[str]
    analyzer_config: AnalyzerConfig = AnalyzerConfig(use_sentiment_model=False)

    class Config:
        arbitrary_types_allowed = True


class ClassifierResponse(BaseModel):
    data: List[Dict[str, float]]


class TaskConfig(BaseModel):
    source_config: Union[TwitterSourceConfig]
    sink_config: Union[HttpSinkConfig, JiraSinkConfig, ElasticSearchSinkConfig, DailyGetSinkConfig]
    analyzer_config: AnalyzerConfig = AnalyzerConfig(use_sentiment_model=False)
    time_in_seconds: int

    def to_json(self):
        return json.dumps(self, default=lambda o: o.__dict__, sort_keys=True, indent=4)

    class Config:
        arbitrary_types_allowed = True
        schema_extra = {
            "example": {
                "source_config": TwitterSourceConfig(
                    keywords=["machine_leanring"],
                    hashtags=["#ai"],
                    usernames=["@user1"],
                    operators=["-is:reply", "-is:retweet"],
                    since_id=1234,
                    until_id=9999,
                    lookup_period="1d",
                    tweet_fields=["author_id", "conversation_id", "created_at", "id", "public_metrics", "text"],
                    user_fields=["id", "name", "public_metrics", "username", "verified"],
                    expansions=["author_id"],
                    place_fields=["country"],
                    max_tweets=10,
                    credential=TwitterCredentials(
                        bearer_token="<twitter_bearer_token>"
                    )
                ).dict(),
                "sink_config": DailyGetSinkConfig(
                    url="http://127.0.0.1:8080/endpoint",
                    partner_id="12345",
                    consumer_phone_number="1234567890",
                    source_information="Twitter",
                    base_payload={
                        "partnerId": "12345",
                        "consumerPhoneNumber": "1234567890",
                    }
                ).dict(),
                "analyzer_config": AnalyzerConfig(
                    labels=["service", "quality", "tracking"],
                    use_sentiment_model=True,
                    multi_class_classification=False
                ).dict(),
                "time_in_seconds": 300
            }
        }


class ScheduleResponse(BaseModel):
    id: str
    run_frequency: str
    next_run: str

    class Config:
        arbitrary_types_allowed = True


class TaskDetail(BaseModel):
    id: Optional[str]
    config: TaskConfig

    class Config:
        arbitrary_types_allowed = True
        response_model_exclude_unset = True


class TaskAddResponse(BaseModel):
    id: str
