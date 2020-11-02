import logging
import os
import sys
from pathlib import Path

from obsei.sink.http_sink_config import HttpSinkConfig
from obsei.sink.http_sink import HttpSink
from obsei.source.twitter_source_config import TwitterSourceConfig
from obsei.source.twitter_source import TwitterSource
from obsei.text_analyzer import TextAnalyzer

logger = logging.getLogger(__name__)
logging.basicConfig(stream=sys.stdout, level=logging.INFO)


sink_config = HttpSinkConfig(
    url=os.environ['DAILYGET_URL'],
    base_payload={
        "partnerId": os.environ['DAILYGET_PARTNER_ID'],
        "consumerPhoneNumber": os.environ['DAILYGET_CONSUMER_NUMBER'],
    },
    payload_mapping={
      "processed_text": ["enquiryMessage"],
      "classification": ["enquiryMessage"],
      "meta": ["enquiryMessage"],
    },
    field_conversion={
        "enquiryMessage": "flat_string"
    }
)

dir_path = Path(__file__).resolve().parent.parent
source_config = TwitterSourceConfig(
    twitter_config_filename=f'{dir_path}/config/twitter.yaml',
    keywords=[os.environ['DAILYGET_QUERY']],
    lookup_period=os.environ['DAILYGET_LOOKUP_PERIOD'],
    tweet_fields=["author_id", "conversation_id", "created_at", "id", "public_metrics", "text"],
    user_fields=["id", "name", "public_metrics", "username", "verified"],
    # tweet_fields=["author_id", "created_at", "id", "public_metrics", "text"],
    # tweet_fields=None,
    # user_fields=None,
    expansions=None,
    place_fields=None,
    max_tweets=10,
)

source = TwitterSource()
sink = HttpSink()
text_analyzer = TextAnalyzer(
    classifier_model_name="facebook/bart-large-mnli",
 #   classifier_model_name="joeddav/xlm-roberta-large-xnli",
    initialize_model=True,
)

source_response_list = source.lookup(source_config)
for idx, source_response in enumerate(source_response_list):
    logger.info(f"source_response#'{idx}'='{source_response.__dict__}'")

analyzer_response_list = text_analyzer.analyze_input(
    source_response_list=source_response_list,
    labels=["experience", "service", "comfortable", "delivery", "delay", "customer care", "response", "frustration"]
)
for idx, analyzer_response in enumerate(analyzer_response_list):
    logger.info(f"analyzer_response#'{idx}'='{analyzer_response.__dict__}'")

sink_response_list = sink.send_data(analyzer_response_list, sink_config)
for sink_response in sink_response_list:
    if sink_response is not None:
        logger.info(f"sink_response='{sink_response.__dict__}'")
