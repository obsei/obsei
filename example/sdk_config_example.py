import logging
import sys

from obsei.configuration import ObseiConfiguration

logger = logging.getLogger(__name__)
logging.basicConfig(stream=sys.stdout, level=logging.INFO)

obsei_configuration = ObseiConfiguration(
    config_path="../config",
    config_filename="sdk.yaml",
)

twitter_source_config = obsei_configuration.get_twitter_source_config()
http_sink_config = obsei_configuration.get_http_sink_config()
daily_get_sink_config = obsei_configuration.get_daily_get_sink_config()
# docker run -d --name elasticsearch -p 9200:9200 -e "discovery.type=single-node" elasticsearch:7.9.2
elasticsearch_sink_config = obsei_configuration.get_elasticsearch_sink_config()
# Start jira server locally `atlas-run-standalone --product jira`
jira_sink_config = obsei_configuration.get_jira_sink_config()
text_analyzer = obsei_configuration.get_text_analyzer()
analyzer_config = obsei_configuration.get_analyzer_config()




