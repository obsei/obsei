import pandas as pd

from obsei.source.pandas_source import (
    PandasSourceConfig,
    PandasSource,
)
import logging
import sys

logger = logging.getLogger(__name__)
logging.basicConfig(stream=sys.stdout, level=logging.INFO)

# Initialize your Pandas DataFrame from your sources like csv, excel, sql etc
# In following example we are reading csv which have two columns title and text
csv_file = "https://raw.githubusercontent.com/deepset-ai/haystack/master/tutorials/small_generator_dataset.csv"
dataframe = pd.read_csv(csv_file)

source_config = PandasSourceConfig(
    dataframe=dataframe,
    include_columns=["title"],
    text_columns=["text"],
)
source = PandasSource()

source_response_list = source.lookup(source_config)
for idx, source_response in enumerate(source_response_list):
    logger.info(f"source_response#'{idx}'='{source_response.__dict__}'")
