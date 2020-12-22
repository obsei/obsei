import logging
from typing import Optional

from obsei.sink.base_sink import BaseSink, BaseSinkConfig
from obsei.source.base_source import BaseSource, BaseSourceConfig
from obsei.analyzer.text_analyzer import AnalyzerConfig, TextAnalyzer

logger = logging.getLogger(__name__)


class Processor:
    def __init__(
        self,
        text_analyzer: TextAnalyzer,
        source: BaseSource = None,
        source_config: BaseSourceConfig = None,
        sink: BaseSink = None,
        sink_config: BaseSinkConfig = None,
    ):
        self.source = source
        self.source_config = source_config
        self.sink = sink
        self.sink_config = sink_config
        self.text_analyzer = text_analyzer

    def process(
        self,
        source: Optional[BaseSource] = None,
        source_config: Optional[BaseSourceConfig] = None,
        sink: Optional[BaseSink] = None,
        sink_config: Optional[BaseSinkConfig] = None,
        analyzer_config: AnalyzerConfig = None
    ):
        source = source or self.source
        source_config = source_config or self.source_config
        sink = sink or self.sink
        sink_config = sink_config or self.sink_config

        source_response_list = source.lookup(config=source_config)
        for idx, source_response in enumerate(source_response_list):
            logger.info(f"source_response#'{idx}'='{source_response}'")

        analyzer_response_list = self.text_analyzer.analyze_input(
            source_response_list=source_response_list,
            analyzer_config=analyzer_config
        )
        for idx, analyzer_response in enumerate(analyzer_response_list):
            logger.info(f"source_response#'{idx}'='{analyzer_response}'")

        sink_response_list = sink.send_data(
            analyzer_responses=analyzer_response_list,
            config=sink_config
        )
        for idx, sink_response in enumerate(sink_response_list):
            logger.info(f"source_response#'{idx}'='{sink_response}'")
