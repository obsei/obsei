import logging
from typing import Any, Dict, Optional

import yaml
from pydantic import BaseSettings, Field, constr

from obsei.analyzer.base_analyzer import BaseAnalyzer, BaseAnalyzerConfig
from obsei.misc.utils import dict_to_object
from obsei.sink.dailyget_sink import DailyGetSinkConfig
from obsei.sink.elasticsearch_sink import ElasticSearchSinkConfig
from obsei.sink.http_sink import HttpSinkConfig
from obsei.sink.jira_sink import JiraSinkConfig
from obsei.source.playstore_reviews import PlayStoreConfig
from obsei.source.twitter_source import TwitterSourceConfig

logger = logging.getLogger(__name__)


class ObseiConfiguration(BaseSettings):
    configuration: Optional[Dict[str, Any]] = None
    config_path: Optional[constr(min_length=1)] = Field(None, env="obsei_config_path")
    config_filename: Optional[constr(min_length=1)] = Field(
        None, env="obsei_config_filename"
    )

    def __init__(self, **data: Any):
        super().__init__(**data)

        if self.configuration is None:
            self.configuration = yaml.load(
                open(f"{self.config_path}/{self.config_filename}", "r"),
                Loader=yaml.FullLoader,
            )
        logger.debug(f"Configuration: {self.configuration}")

    def initialize_instance(self, key_name: str = None):
        if (
            key_name is None
            or key_name not in self.configuration
            or not self.configuration[key_name]
        ):
            logger.warning(f"{key_name} not exist in configuration")
            return None
        return dict_to_object(self.configuration[key_name])

    def get_twitter_source_config(
        self, key_name: str = "twitter_source"
    ) -> TwitterSourceConfig:
        return self.initialize_instance(key_name)

    def get_play_store_source_config(
        self, key_name: str = "play_store_source"
    ) -> PlayStoreConfig:
        return self.initialize_instance(key_name)

    def get_http_sink_config(self, key_name: str = "http_sink") -> HttpSinkConfig:
        return self.initialize_instance(key_name)

    def get_daily_get_sink_config(
        self, key_name: str = "daily_get_sink"
    ) -> DailyGetSinkConfig:
        return self.initialize_instance(key_name)

    def get_elasticsearch_sink_config(
        self, key_name: str = "elasticsearch_sink"
    ) -> ElasticSearchSinkConfig:
        return self.initialize_instance(key_name)

    def get_jira_sink_config(self, key_name: str = "jira_sink") -> JiraSinkConfig:
        return self.initialize_instance(key_name)

    def get_analyzer(self, key_name: str = "analyzer") -> BaseAnalyzer:
        return self.initialize_instance(key_name)

    def get_analyzer_config(
        self, key_name: str = "analyzer_config"
    ) -> BaseAnalyzerConfig:
        return self.initialize_instance(key_name)

    def get_logging_config(self, key_name: str = "logging") -> Dict[str, Any]:
        return self.configuration[key_name]
