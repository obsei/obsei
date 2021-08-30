from typing import List, Optional, Any

from pandas import DataFrame

from obsei.source.base_source import BaseSource, BaseSourceConfig
from obsei.payload import TextPayload


class PandasSourceConfig(BaseSourceConfig):
    TYPE: str = "Pandas"

    dataframe: DataFrame
    text_columns: List[str]
    separator: str = " "
    include_columns: Optional[List[str]] = None

    def __init__(self, **data: Any):
        super().__init__(**data)

        if len(self.text_columns) == 0:
            raise ValueError("`text_columns` cannot be empty")

        if not all(
            [text_column in self.dataframe.columns for text_column in self.text_columns]
        ):
            raise ValueError("Every `text_columns` should be present in `dataframe`")

        try:
            self.dataframe[self.text_columns] = self.dataframe[
                self.text_columns
            ].astype("string")
        except TypeError as e:
            raise ValueError("Unable to convert `text_columns` to string dtype")


class PandasSource(BaseSource):
    NAME: Optional[str] = "Pandas"

    def lookup(self, config: PandasSourceConfig, **kwargs) -> List[TextPayload]:  # type: ignore[override]
        df_to_records = config.dataframe.to_dict("records")
        source_responses: List[TextPayload] = [
            TextPayload(
                processed_text=config.separator.join(
                    [record.get(text_column) for text_column in config.text_columns]
                ),
                meta={key: record[key] for key in config.include_columns}
                if config.include_columns is not None
                else record,
                source_name=self.NAME,
            )
            for record in df_to_records
        ]

        return source_responses
