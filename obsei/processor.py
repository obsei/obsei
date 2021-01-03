import logging
from typing import Optional

from obsei.sink.base_sink import BaseSink, BaseSinkConfig
from obsei.source.base_source import BaseSource, BaseSourceConfig
from obsei.analyzer.text_analyzer import AnalyzerConfig, TextAnalyzer
from obsei.workflow.workflow import Workflow

logger = logging.getLogger(__name__)


class Processor:
    def __init__(
        self,
        text_analyzer: TextAnalyzer,
        analyzer_config: AnalyzerConfig,
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
        self.analyzer_config = analyzer_config

    def process(
        self,
        workflow: Optional[Workflow] = None,
        source: Optional[BaseSource] = None,
        sink: Optional[BaseSink] = None,
        text_analyzer: Optional[TextAnalyzer] = None
    ):
        source = source or self.source
        sink = sink or self.sink
        text_analyzer = text_analyzer or self.text_analyzer

        id: Optional[str] = None
        if workflow:
            sink_config = workflow.config.sink_config
            source_config = workflow.config.source_config
            analyzer_config = workflow.config.analyzer_config
            id = workflow.id
        else:
            sink_config = self.sink_config
            source_config = self.source_config
            analyzer_config = self.analyzer_config

        source_response_list = source.lookup(
            config=source_config,
            id=id
        )
        for idx, source_response in enumerate(source_response_list):
            logger.info(f"source_response#'{idx}'='{source_response}'")

        analyzer_response_list = text_analyzer.analyze_input(
            source_response_list=source_response_list,
            analyzer_config=analyzer_config,
            id=id
        )
        for idx, analyzer_response in enumerate(analyzer_response_list):
            logger.info(f"source_response#'{idx}'='{analyzer_response}'")

        sink_response_list = sink.send_data(
            analyzer_responses=analyzer_response_list,
            config=sink_config,
            id=id
        )
        for idx, sink_response in enumerate(sink_response_list):
            logger.info(f"source_response#'{idx}'='{sink_response}'")
