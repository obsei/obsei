# Jira Sink
import logging
import sys
from pathlib import Path

from pydantic import SecretStr

from obsei.sink.jira_sink import JiraSink, JiraSinkConfig
from obsei.source.twitter_source import TwitterSource, TwitterSourceConfig
from obsei.text_analyzer import AnalyzerConfig, TextAnalyzer

logger = logging.getLogger(__name__)
logging.basicConfig(stream=sys.stdout, level=logging.INFO)

dir_path = Path(__file__).resolve().parent.parent
source_config = TwitterSourceConfig(
    keywords=["text-classification"],
    lookup_period="15m",
    tweet_fields=["author_id", "conversation_id", "created_at", "id", "public_metrics", "text"],
    user_fields=["id", "name", "public_metrics", "username", "verified"],
    expansions=["author_id"],
    place_fields=None,
    max_tweets=10,
)

source = TwitterSource()

# Start jira server locally `atlas-run-standalone --product jira`
jira_sink_config = JiraSinkConfig(
    url="http://localhost:2990/jira",
    username=SecretStr("user"),
    password=SecretStr("pass"),
    issue_type={"name": "Task"},
    project={"key": "CUS"},
)
jira_sink = JiraSink()

text_analyzer = TextAnalyzer(
    model_name_or_path="joeddav/bart-large-mnli-yahoo-answers",
 #   model_name_or_path="joeddav/xlm-roberta-large-xnli",
    initialize_model=True,
    analyzer_config=AnalyzerConfig(
        labels=["service", "delay", "tracking", "no response", "missing items", "delivery", "mask"],
        use_sentiment_model=True
    )
)

source_response_list = source.lookup(source_config)
for idx, source_response in enumerate(source_response_list):
    logger.info(f"source_response#'{idx}'='{source_response.__dict__}'")

analyzer_response_list = text_analyzer.analyze_input(
    source_response_list=source_response_list
)
for idx, an_response in enumerate(analyzer_response_list):
    logger.info(f"analyzer_response#'{idx}'='{an_response.__dict__}'")

sink_response_list = jira_sink.send_data(analyzer_response_list, jira_sink_config)
for sink_response in sink_response_list:
    if sink_response is not None:
        logger.info(f"sink_response='{sink_response}'")
