import logging
from obsei import configuration
from typing import List, Optional ,Dict, Any

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
# ret_payload = payload.TextPayload()

# path = "t1.csv"
# # column news- target date editor 
# df = pd.read_csv(path)

# str = df['news'][0]#" there was an accident "


# # re ={
# #     str: "sfgsd",
# #     meta : {editor : "time"}
# # }
# # # combine all rows text
class PandasSourceConfig(BaseSourceConfig):
    TYPE: str = "PandasScrapper"
    
    
    def __init__(self, **data: Any):
        super().__init__(**data)

        self.target = data.get('target',None)
        self.input_type: str = data.get('input_type',None)# "csv"
        self.rows: Optional[int] = data.get('rows',None)
        self.columns: Optional[list] = data.get('columns',None)

        # supported_formats = ["csv","dataframe","excel"]
    
    
class PandasSourceScrapper(BaseSource):
    NAME: Optional[str] = "PandasSourceScrapper"

    def lookup (  # type: ignore[override]
        self, config: PandasSourceConfig, **kwargs) -> List[TextPayload]:
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

        
        supported_formats = ["csv","dataframe","excel"]
        if config.input_type not in supported_formats :
            logger.warning("input type can only be a pandas dataframe, csv or and excel sheet")
            return source_responses

        #where path to csv is a target
        if config.input_type == "csv":
            if config.rows is not None and config.columns is not None:
                df = pd.read_csv(config.target,nrows=config.rows,usecols=config.columns)
            elif config.columns is not None and config.rows is None:
                df= pd.read_csv(config.target,usecols=config.columns)
            else:
                df = pd.read_csv(config.target)

        #where target is direct pandas dataframe
        elif config.input_type == "dataframe":
            if config.columns is not None:
                df = config.target[config.columns]
            else:
                df = config.target
        
        #where target is an excel sheet
        elif config.input_type == "excel":

            if config.rows is not None and config.columns is not None:
                df = pd.read_excel(config.target,nrows=config.rows,usecols=config.columns)
            elif config.columns is not None and config.rows is None:
                df= pd.read_excel(config.target,usecols=config.columns)
            else:
                df = pd.read_excel(config.target)
                # print(df.head(10))
        
        #use to_dict function dont do it by iterating over everything
        #The rest of project has used list of dictionaries as return not a dictionary of dictionary
        # df["source_name"] = self.NAME

        # res = df.to_dict('records')

        
