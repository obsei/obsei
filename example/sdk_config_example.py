import logging
import os
import sys

from obsei.configuration import ObseiConfiguration

logger = logging.getLogger(__name__)
logging.basicConfig(stream=sys.stdout, level=logging.INFO)

os.environ["twitter_bearer_token"] = "twitter_bearer_token"

obsei_configuration = ObseiConfiguration(
    config_path="../config",
    config_filename="sdk.yaml",
)

twitter_source_config = obsei_configuration.get_twitter_source_config()
http_sink_config = obsei_configuration.get_http_sink_config()
daily_get_sink_config = obsei_configuration.get_daily_get_sink_config()
elasticsearch_sink_config = obsei_configuration.get_elasticsearch_sink_config()
analyzer_config = obsei_configuration.get_analyzer_config()
text_analyzer = obsei_configuration.get_text_analyzer()


