import logging
from typing import Optional

from pydantic import BaseModel

from obsei.analyzer.base_analyzer import BaseAnalyzer, BaseAnalyzerConfig
from obsei.sink.base_sink import BaseSink, BaseSinkConfig
from obsei.source.base_source import BaseSource, BaseSourceConfig
from obsei.workflow.workflow import Workflow

logger = logging.getLogger(__name__)


class Processor(BaseModel):
    analyzer: BaseAnalyzer
    analyzer_config: Optional[BaseAnalyzerConfig] = None
    source: Optional[BaseSource] = None
    source_config: Optional[BaseSourceConfig] = None
    sink: Optional[BaseSink] = None
    sink_config: Optional[BaseSinkConfig] = None

    def process(
        self,
        workflow: Optional[Workflow] = None,
        source: Optional[BaseSource] = None,
        source_config: Optional[BaseSourceConfig] = None,
        sink: Optional[BaseSink] = None,
        sink_config: Optional[BaseSinkConfig] = None,
        analyzer: Optional[BaseAnalyzer] = None,
        analyzer_config: Optional[BaseAnalyzerConfig] = None,
    ):
        source = source or self.source
        sink = sink or self.sink
        analyzer = analyzer or self.analyzer

        id: Optional[str] = None
        if workflow:
            sink_config = workflow.config.sink_config
            source_config = workflow.config.source_config
            analyzer_config = workflow.config.analyzer_config
            id = workflow.id
        else:
            sink_config = sink_config or self.sink_config
            source_config = source_config or self.source_config
            analyzer_config = analyzer_config or self.analyzer_config

        if source is None or source_config is None:
            return
        if sink is None or sink_config is None:
            return

        source_response_list = source.lookup(config=source_config, id=id)
        for idx, source_response in enumerate(source_response_list):
            logger.info(f"source_response#'{idx}'='{source_response}'")

        analyzer_response_list = analyzer.analyze_input(
            source_response_list=source_response_list,
            analyzer_config=analyzer_config,
            id=id,
        )
        for idx, analyzer_response in enumerate(analyzer_response_list):
            logger.info(f"source_response#'{idx}'='{analyzer_response}'")

        sink_response_list = sink.send_data(
            analyzer_responses=analyzer_response_list, config=sink_config, id=id
        )
        for idx, sink_response in enumerate(sink_response_list):
            logger.info(f"source_response#'{idx}'='{sink_response}'")
