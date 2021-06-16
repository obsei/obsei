import logging
from logging import Logger
from typing import Any, List, Optional

from pydantic import Field

from obsei.payload import TextPayload
from obsei.sink.base_sink import BaseSink, BaseSinkConfig, Convertor


class LoggerSinkConfig(BaseSinkConfig):
    TYPE: str = "Logging"
    logger: Logger = Field(logging.getLogger(__name__))
    level: int = Field(logging.INFO)


class LoggerSink(BaseSink):
    TYPE: str = "Logging"

    def __init__(self, convertor: Convertor = Convertor(), **data: Any):
        super().__init__(convertor=convertor, **data)

    def send_data(  # type: ignore[override]
        self,
        analyzer_responses: List[TextPayload],
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
                vars(response) if hasattr(response, "__dict__") else response
            )
            config.logger.log(level=config.level, msg=f"{dict_to_print}")
