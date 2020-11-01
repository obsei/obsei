import logging
import sys

from obsei.sink.http_sink_config import HttpSinkConfig
from obsei.sink.http_sink import HttpSink
from obsei.source.twitter_source_config import TwitterSourceConfig
from obsei.source.twitter_source import TwitterSource
from obsei.text_analyzer import TextAnalyzer

logger = logging.getLogger(__name__)
logging.basicConfig(stream=sys.stdout, level=logging.INFO)


sink_config = HttpSinkConfig(
    url="<URL>",
    base_payload={
        "partnerId": <ID>,
    },
    payload_mapping={
      "text": ["enquiryMessage", "text"],
      "sentiment_value": ["enquiryMessage", "sentiment_value"],
      "sentiment_type": ["enquiryMessage", "sentiment_type"],
      "classification_map": ["enquiryMessage", "classification_map"],
      "meta_information": ["enquiryMessage", "meta_information"],
    }
)

source_config = TwitterSourceConfig(
    twitter_config_filename="../config/twitter.yaml", # "~/.twitter_keys.yaml",
    query="XpressBees",
    lookup_period="7d",
    tweet_fields=None,
    operators=None,
    user_fields=None,
    expansions=None,
    place_fields=None,
    max_tweets=10,
)

source = TwitterSource()
sink = HttpSink()
text_analyzer = TextAnalyzer(
    initialize_sentiment_model=False,
)

source_response_list = source.lookup(source_config)
for idx, source_response in enumerate(source_response_list):
    logger.info(f"source_response#'{idx}'='{source_response.__dict__}'")

analyzer_response_list = text_analyzer.analyze_input(source_response_list)
for idx, analyzer_response in enumerate(analyzer_response_list):
    logger.info(f"source_response#'{idx}'='{analyzer_response.__dict__}'")

sink_response_list = sink.send_data(analyzer_response_list, sink_config)
for idx, sink_response in enumerate(sink_response_list):
    logger.info(f"source_response#'{idx}'='{sink_response.__dict__}'")
