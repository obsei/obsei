import logging

from numpy import dtype
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
    TYPE: str = "Pandas"
    
    dataframe: Optional[pd.DataFrame] = None
    include_columns_list: Optional[List[str]] = None
    # Text columns
    text_columns_list: List[str]
    # rows: Optional[int] = None
    

    def __init__(self, **data: Any):
        super().__init__(**data)
        
        allowed_dtype = "object"
        dtype_list = self.dataframe[self.text_columns_list].dtypes.to_dict()
        #Cheking if target cols are of type object(string)
        for col_name, typ in dtype_list.items():
            if (typ != allowed_dtype): 
                logger.warning(f"`dataframe['{col_name}'].dtype == {typ}` not {allowed_dtype}")

        # if(self.dataframe[self.include_columns_list] != )



class PandasSourceScrapper(BaseSource):
    NAME: Optional[str] = "PandasSourceScrapper"

    def lookup(  # type: ignore[override]
        self, config: PandasSourceConfig, **kwargs
    ) -> List[TextPayload]:
        source_responses: List[TextPayload] = []

      
        # now we parse data as per textpayload specifications

        if config.include_columns_list is not None:   #this case when target cols is mentioned
            ret_df = pd.DataFrame(columns=["text_payload"])
            for tar_col in config.include_columns_list:
                meta_col = [x for x in config.dataframe.columns if x != tar_col]# Apply uses cython hence faster than looping directly
                ret_df["text_payload"] = config.dataframe.apply(lambda x: self.parse_util(target_col=x[tar_col],meta_list =x[meta_col]),axis=1)
                res_list = ret_df.to_records(index=False)
                for x in res_list:
                    source_responses.append(x[0])
        else:                                        #This case when no target cols are mentioned I have parsed all text cols
            ret_df = pd.DataFrame(columns=["text_payload"])
            for tar_col in config.text_columns_list:
                meta_col = [x for x in config.dataframe.columns if x != tar_col]
                ret_df["text_payload"] = config.dataframe.apply(lambda x: self.parse_util(target_col=x[tar_col],meta_list =x[meta_col]),axis=1)
                res_list = ret_df.to_records(index=False)
                for x in res_list:
                    source_responses.append(x[0])
         
        return source_responses

    def parse_util(self, target_col,meta_list):

        return TextPayload(
                            processed_text=str(target_col),
                            meta=meta_list,
                            # {
                            #     non_target: row[non_target]
                            #     for non_target in meta_list
                            # },
                            source_name=self.NAME,
        )