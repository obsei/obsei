import logging
import sys

from obsei.configuration import ObseiConfiguration

logger = logging.getLogger(__name__)
logging.basicConfig(stream=sys.stdout, level=logging.INFO)

obsei_configuration = ObseiConfiguration(
    config_path="../example",
    config_filename="sdk.yaml",
)

text_analyzer = obsei_configuration.initialize_instance("analyzer")
analyzer_config = obsei_configuration.initialize_instance("analyzer_config")
slack_source_config = obsei_configuration.initialize_instance("slack_sink_config")
slack_sink = obsei_configuration.initialize_instance("slack_sink")

play_store_source_config = obsei_configuration.initialize_instance("play_store_source")
twitter_source_config = obsei_configuration.initialize_instance("twitter_source")
http_sink_config = obsei_configuration.initialize_instance("http_sink")
daily_get_sink_config = obsei_configuration.initialize_instance("daily_get_sink")
# docker run -d --name elasticsearch -p 9200:9200 -e "discovery.type=single-node" elasticsearch:7.9.2
elasticsearch_sink_config = obsei_configuration.initialize_instance(
    "elasticsearch_sink"
)
# Start jira server locally `atlas-run-standalone --product jira`
jira_sink_config = obsei_configuration.initialize_instance("jira_sink")
