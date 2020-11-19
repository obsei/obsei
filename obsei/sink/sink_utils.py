from obsei.sink.base_sink import BaseSink
from obsei.sink.dailyget_sink import DailyGetSink
from obsei.sink.elasticsearch_sink import ElasticSearchSink
from obsei.sink.http_sink import HttpSink
from obsei.sink.jira_sink import JiraSink

sink_map = {
    "Http": HttpSink(),  # type: BaseSink
    "Jira": JiraSink(),  # type: BaseSink
    "DailyGet": DailyGetSink(),  # type: BaseSink
    "Elasticsearch": ElasticSearchSink(),  # type: BaseSink
}
