from typing import Any

from hydra.experimental import compose, initialize
from pydantic import BaseSettings, Field, constr

from obsei.sink.dailyget_sink import DailyGetSinkConfig
from obsei.sink.elasticsearch_sink import ElasticSearchSinkConfig
from obsei.sink.http_sink import HttpSinkConfig
from obsei.source.twitter_source import TwitterSourceConfig
from obsei.text_analyzer import AnalyzerConfig, TextAnalyzer


class ObseiConfiguration(BaseSettings):
    __slots__ = ('configuration',)
    config_path: constr(min_length=1) = Field(None, env='obsei_config_path')
    config_filename: constr(min_length=1) = Field(None, env='obsei_config_filename')

    def __init__(self, **data: Any):
        super().__init__(**data)
        with initialize(config_path=self.config_path):
            object.__setattr__(
                self,
                'configuration',
                compose(self.config_filename)
            )

    def get_twitter_source_config(self, key_name: str = None) -> TwitterSourceConfig:
        key_name = key_name if key_name is not None else "twitter_source"
        return TwitterSourceConfig(**self.configuration[key_name])

    def get_http_sink_config(self, key_name: str = None) -> HttpSinkConfig:
        key_name = key_name if key_name is not None else "http_sink"
        return HttpSinkConfig(**self.configuration[key_name])

    def get_daily_get_sink_config(self, key_name: str = None) -> DailyGetSinkConfig:
        key_name = key_name if key_name is not None else "daily_get_sink"
        return DailyGetSinkConfig(**self.configuration[key_name])

    def get_elasticsearch_sink_config(self, key_name: str = None) -> ElasticSearchSinkConfig:
        key_name = key_name if key_name is not None else "elasticsearch_sink"
        return ElasticSearchSinkConfig(**self.configuration[key_name])

    def get_text_analyzer(self, key_name: str = None) -> TextAnalyzer:
        key_name = key_name if key_name is not None else "text_analyzer"
        return TextAnalyzer(**self.configuration[key_name])

    def get_analyzer_config(self, key_name: str = None) -> AnalyzerConfig:
        key_name = key_name if key_name is not None else "analyzer_config"
        return AnalyzerConfig(**self.configuration[key_name])
