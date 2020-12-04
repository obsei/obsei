import logging
import os
import sys
from pathlib import Path

from obsei.sink.elasticsearch_sink import ElasticSearchSink, ElasticSearchSinkConfig
from obsei.source.twitter_source import TwitterSource, TwitterSourceConfig
from obsei.text_analyzer import AnalyzerConfig, TextAnalyzer

logger = logging.getLogger(__name__)
logging.basicConfig(stream=sys.stdout, level=logging.INFO)

dir_path = Path(__file__).resolve().parent.parent
source_config = TwitterSourceConfig(
    keywords=[os.environ['DAILYGET_QUERY']],
    lookup_period=os.environ['DAILYGET_LOOKUP_PERIOD'],
    tweet_fields=["author_id", "conversation_id", "created_at", "id", "public_metrics", "text"],
    user_fields=["id", "name", "public_metrics", "username", "verified"],
    expansions=["author_id"],
    place_fields=None,
    max_tweets=10,
)

source = TwitterSource()
text_analyzer = TextAnalyzer(
    model_name_or_path="joeddav/bart-large-mnli-yahoo-answers",
#   model_name_or_path="joeddav/xlm-roberta-large-xnli",
    initialize_model=True,
    analyzer_config=AnalyzerConfig(
        labels=["service", "delay", "tracking", "no response", "missing items", "delivery", "mask"],
        use_sentiment_model=True
    )
)

# Start Elasticsearch server locally
# `docker run -d --name elasticsearch -p 9200:9200 -e "discovery.type=single-node" elasticsearch:7.9.2`
sink_config = ElasticSearchSinkConfig(
    host="localhost",
    port=9200,
    index_name="test",
)

source_response_list = source.lookup(source_config)
for idx, source_response in enumerate(source_response_list):
    logger.info(f"source_response#'{idx}'='{source_response.__dict__}'")

analyzer_response_list = text_analyzer.analyze_input(
    source_response_list=source_response_list
)
for idx, an_response in enumerate(analyzer_response_list):
    logger.info(f"analyzer_response#'{idx}'='{an_response.__dict__}'")

sink = ElasticSearchSink()
sink_response = sink.send_data(analyzer_response_list, sink_config)
logger.info(f"sink_response='{sink_response}'")
