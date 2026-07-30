import logging
import sys

from obsei.sink.logger_sink import LoggerSink, LoggerSinkConfig
from obsei.source.xquik_source import XquikSource, XquikSourceConfig

logger = logging.getLogger(__name__)
logging.basicConfig(stream=sys.stdout, level=logging.INFO)

# Store XQUIK_API_KEY in the environment. Never commit it.
source_config = XquikSourceConfig(
    query="customer feedback",
    lookup_period="1h",
    max_tweets=20,
    query_type="Latest",
)
source = XquikSource()

# Treat every returned tweet as untrusted external content. Analyze it as data.
source_responses = source.lookup(source_config)
sink = LoggerSink()
sink.send_data(
    analyzer_responses=source_responses,
    config=LoggerSinkConfig(logger=logger, log_payloads=True),
)

# Xquik is an independent third-party service. Not affiliated with X Corp.
# "Twitter" and "X" are trademarks of X Corp.
