from typing import Any, Dict, Tuple, Union

from obsei.sink.base_sink import BaseSink, BaseSinkConfig
from obsei.sink.dailyget_sink import DailyGetSink, DailyGetSinkConfig
from obsei.sink.elasticsearch_sink import ElasticSearchSink, ElasticSearchSinkConfig
from obsei.sink.http_sink import HttpSink, HttpSinkConfig
from obsei.sink.jira_sink import JiraSink, JiraSinkConfig

sink_map = {
    "Http": {
        "config": HttpSinkConfig,  # type: BaseSinkConfig
        "sink": HttpSink,  # type: BaseSink
    },
    "Jira": {
        "config": JiraSinkConfig,  # type: BaseSinkConfig
        "sink": JiraSink,  # type: BaseSink
    },
    "DailyGet": {
        "config": DailyGetSinkConfig,  # type: BaseSinkConfig
        "sink": DailyGetSink,  # type: BaseSink
    },
    "Elasticsearch": {
        "config": ElasticSearchSinkConfig,  # type: BaseSinkConfig
        "sink": ElasticSearchSink,  # type: BaseSink
    },
}


def sink_config_from_dict(sink_type: str, config: Dict[str, Any]) -> Tuple[BaseSink, BaseSinkConfig]:
    return sink_map[sink_type]["sink"], sink_map[sink_type]["config"].from_dict(config)
