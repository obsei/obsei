from obsei.source.pandas import (
    PandasSourceConfig,
    PandasSourceScrapper,
)
import logging
import sys
import pandas as pd


path = "glass1.csv"
df = pd.read_csv(path)

logger = logging.getLogger(__name__)
logging.basicConfig(stream=sys.stdout, level=logging.INFO)

source_config = PandasSourceConfig(
    dataframe=df, include_columns_list =["str"],text_columns_list = ["str"]
)
source = PandasSourceScrapper()
source_response_list = source.lookup(source_config)
for idx, source_response in enumerate(source_response_list):
    logger.info(f"source_response#'{idx}'='{source_response.__dict__}'")
