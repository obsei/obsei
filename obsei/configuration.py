import logging
from typing import Any

from hydra.experimental import compose, initialize
from hydra.utils import instantiate
from omegaconf import DictConfig, OmegaConf
from pydantic import BaseSettings, Field, constr

from obsei.sink.dailyget_sink import DailyGetSinkConfig
from obsei.sink.elasticsearch_sink import ElasticSearchSinkConfig
from obsei.sink.http_sink import HttpSinkConfig
from obsei.sink.jira_sink import JiraSinkConfig
from obsei.source.playstore_reviews import PlayStoreConfig
from obsei.source.twitter_source import TwitterSourceConfig
from obsei.analyzer.text_analyzer import AnalyzerConfig, TextAnalyzer

logger = logging.getLogger(__name__)


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
            logger.debug("Configuration: \n" + OmegaConf.to_yaml(self.configuration))

    def initialize_instance(self, key_name: str = None):
        return instantiate(self.configuration[key_name], _recursive_=True)

    def get_twitter_source_config(self, key_name: str = "twitter_source") -> TwitterSourceConfig:
        return self.initialize_instance(key_name)

    def get_play_store_source_config(self, key_name: str = "play_store_source") -> PlayStoreConfig:
        return self.initialize_instance(key_name)

    def get_http_sink_config(self, key_name: str = "http_sink") -> HttpSinkConfig:
        return self.initialize_instance(key_name)

    def get_daily_get_sink_config(self, key_name: str = "daily_get_sink") -> DailyGetSinkConfig:
        return self.initialize_instance(key_name)

    def get_elasticsearch_sink_config(self, key_name: str = "elasticsearch_sink") -> ElasticSearchSinkConfig:
        return self.initialize_instance(key_name)

    def get_jira_sink_config(self, key_name: str = "jira_sink") -> JiraSinkConfig:
        return self.initialize_instance(key_name)

    def get_text_analyzer(self, key_name: str = "text_analyzer") -> TextAnalyzer:
        return self.initialize_instance(key_name)

    def get_analyzer_config(self, key_name: str = "analyzer_config") -> AnalyzerConfig:
        return self.initialize_instance(key_name)

    def get_logging_config(self, key_name: str = "logging") -> DictConfig:
        return self.configuration[key_name]
