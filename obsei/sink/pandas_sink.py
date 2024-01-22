from typing import Any, Dict, List, Optional

from pandas import DataFrame, concat

from obsei.payload import TextPayload
from obsei.misc.utils import flatten_dict
from obsei.sink.base_sink import BaseSink, BaseSinkConfig, Convertor


class PandasConvertor(Convertor):
    def convert(
        self,
        analyzer_response: TextPayload,
        base_payload: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        base_payload = base_payload or {}
        merged_dict = {**base_payload, **analyzer_response.to_dict()}
        return flatten_dict(merged_dict)


class PandasSinkConfig(BaseSinkConfig):
    TYPE: str = "Pandas"
    dataframe: Optional[DataFrame] = None
    # By default it will include all the columns
    include_columns_list: Optional[List[str]] = None

    def __init__(self, **data: Any):
        super().__init__(**data)

        if self.dataframe is None:
            self.dataframe = DataFrame()


class PandasSink(BaseSink):
    TYPE: str = "Pandas"

    def __init__(self, convertor: Convertor = PandasConvertor(), **data: Any):
        super().__init__(convertor=convertor, **data)

    def send_data(  # type: ignore[override]
        self,
        analyzer_responses: List[TextPayload],
        config: PandasSinkConfig,
        **kwargs: Any,
    ) -> Any:
        responses = []
        for analyzer_response in analyzer_responses:
            converted_response = self.convertor.convert(
                analyzer_response=analyzer_response
            )
            response: Optional[Dict[str, Any]] = None
            if config.include_columns_list:
                response = dict()
                for k, v in converted_response.items():
                    if k in config.include_columns_list:
                        response[k] = v
            else:
                response = converted_response
            responses.append(response)

        if config.dataframe is not None:
            responses_df = DataFrame(responses)
            config.dataframe = concat([config.dataframe, responses_df], ignore_index=True)

        return config.dataframe
