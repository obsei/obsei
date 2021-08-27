import logging
from obsei import configuration
from typing import List, Optional, Dict, Any

from pandas.core.frame import DataFrame
from obsei.source.base_source import BaseSource, BaseSourceConfig
from obsei.payload import TextPayload
from obsei.misc.utils import (
    DATETIME_STRING_PATTERN,
    DEFAULT_LOOKUP_PERIOD,
    convert_utc_time,
)
import pandas as pd

logger = logging.getLogger(__name__)


class PandasSourceConfig(BaseSourceConfig):
    TYPE: str = "PandasScrapper"
    target: str = None
    target_df: Optional[pd.DataFrame] = None
    input_type: str = None
    rows: Optional[int] = None
    columns: list = None

    def __init__(self, **data: Any):
        super().__init__(**data)

        # self.target = None
        # self.input_type: str = None
        # self.rows: Optional[int] = None
        # self.columns: Optional[list] = None


class PandasSourceScrapper(BaseSource):
    NAME: Optional[str] = "PandasSourceScrapper"

    def lookup(  # type: ignore[override]
        self, config: PandasSourceConfig, **kwargs
    ) -> List[TextPayload]:
        source_responses: List[TextPayload] = []

        # Get data from state
        id: str = kwargs.get("id", None)
        state: Optional[Dict[str, Any]] = (
            None
            if id is None or self.store is None
            else self.store.get_source_state(id)
        )
        update_state: bool = True if id else False
        state = state or dict()

        supported_formats = ["csv", "dataframe", "excel"]
        if config.input_type not in supported_formats:
            logger.warning(
                "input type can only be a pandas dataframe, csv or and excel sheet"
            )
            return source_responses

        # where path to csv is a target
        if config.input_type == "csv":
            if config.rows is not None and config.columns is not None:
                df = pd.read_csv(config.target, nrows=config.rows)
            elif config.columns is not None and config.rows is None:
                df = pd.read_csv(config.target)
            else:
                df = pd.read_csv(config.target)

        # where target is direct pandas dataframe
        elif config.input_type == "dataframe":
            if config.columns is not None:
                df = config.target[config.columns]
            else:
                df = config.target

        # where target is an excel sheet
        elif config.input_type == "excel":

            if config.rows is not None and config.columns is not None:
                df = pd.read_excel(config.target, nrows=config.rows)
            elif config.columns is not None and config.rows is None:
                df = pd.read_excel(config.target)
            else:
                df = pd.read_excel(config.target)
                # print(df.head(10))

        # now we parse data as per textpayload specifications

        non_target_col_list = [x for x in df.columns if x not in config.columns]
        for col in config.columns:
            for index, row in df.iterrows():
                source_responses.append(
                    TextPayload(
                        processed_text=str(row[col]),
                        meta={
                            non_target: row[non_target]
                            for non_target in non_target_col_list
                        },
                        source_name=self.NAME,
                    )
                )

        return source_responses
