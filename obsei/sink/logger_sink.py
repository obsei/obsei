import logging
from logging import Logger
from typing import Any, List, Optional

from obsei.analyzer.base_analyzer import AnalyzerResponse
from obsei.sink.base_sink import BaseSink, BaseSinkConfig, Convertor


class LoggerSinkConfig(BaseSinkConfig):
    TYPE: str = "Logging"
    logger: Optional[Logger] = None
    level: Optional[int] = logging.INFO

    def __init__(self, **data: Any):
        super().__init__(**data)
        self.logger = self.logger or logging.getLogger(__name__)


class LoggerSink(BaseSink):
    TYPE: str = "Logging"

    def __init__(self, convertor: Convertor = Convertor(), **data: Any):
        super().__init__(convertor=convertor, **data)

    def send_data(
        self,
        analyzer_responses: List[AnalyzerResponse],
        config: LoggerSinkConfig,
        **kwargs,
    ):
        converted_responses = []
        for analyzer_response in analyzer_responses:
            converted_responses.append(
                self.convertor.convert(analyzer_response=analyzer_response)
            )

        for response in converted_responses:
            dict_to_print = (
                response.__dict__ if hasattr(response, "__dict__") else response
            )
            config.logger.log(level=config.level, msg=f"{dict_to_print}")
