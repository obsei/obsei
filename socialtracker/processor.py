import logging

from socialtracker.sink.base_sink_config import BaseSinkConfig
from socialtracker.source.base_source_config import BaseSourceConfig
from socialtracker.sink.base_sink import BaseSink
from socialtracker.source.base_source import BaseSource
from socialtracker.text_analyzer import TextAnalyzer

logger = logging.getLogger(__name__)


class Processor:
    def __init__(
        self,
        source: BaseSource,
        source_config: BaseSourceConfig,
        sink: BaseSink,
        sink_config: BaseSinkConfig,
        text_analyzer: TextAnalyzer,
    ):
        self.source = source
        self.source_config = source_config
        self.sink = sink
        self.sink_config = sink_config
        self.text_analyzer = text_analyzer

    def process(self):
        source_response_list = self.source.lookup(self.source_config)
        logger.info("source_response_list=", source_response_list)
        analyzer_response_list = self.text_analyzer.analyze_input(source_response_list)
        logger.info("analyzer_response_list=", analyzer_response_list)
        sink_response_list = self.sink.send_data(analyzer_response_list, self.sink_config)
        logger.info("sink_response_list=", sink_response_list)
