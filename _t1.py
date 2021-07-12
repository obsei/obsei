
from obsei.source.website_crawler_source import TrafilaturaCrawlerConfig, TrafilaturaCrawlerSource

# initialize website crawler source config
source_config = TrafilaturaCrawlerConfig(
   urls=['https://simple.wikipedia.org/wiki/Cricket']
)

from time import time
source = TrafilaturaCrawlerSource()

from obsei.analyzer.classification_analyzer import ClassificationAnalyzerConfig, ZeroShotClassificationAnalyzer

analyzer_config=ClassificationAnalyzerConfig(
   labels=["history", "arts", "sports"],
)

text_analyzer = ZeroShotClassificationAnalyzer(
   model_name_or_path="typeform/mobilebert-uncased-mnli",
   device="auto" # change to "cuda:0" for using gpu
)

from obsei.sink.logger_sink import LoggerSink, LoggerSinkConfig
import logging
import sys

logger = logging.getLogger("Obsei")
logging.basicConfig(stream=sys.stdout, level=logging.INFO)

# initialize logger sink config
sink_config = LoggerSinkConfig(
   logger=logger,
   level=logging.INFO
)

# initialize logger sink
sink = LoggerSink()


# This will fetch information from configured source
source_response_list = source.lookup(source_config)

# This will execute analyzer
t1 = time()
analyzer_response_list = text_analyzer.analyze_input(
    source_response_list=source_response_list,
    analyzer_config=analyzer_config
)
t2 = time()

print(t2-t1)
# This will send analyzed output to sink
sink.send_data(analyzer_response_list, sink_config)
# v1 = 13 secs vs 4 seconds
