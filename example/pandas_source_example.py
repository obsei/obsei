from pandas import DataFrame

from obsei.source.pandas_source import (
    PandasSourceConfig,
    PandasSource,
)
import logging
import sys

logger = logging.getLogger(__name__)
logging.basicConfig(stream=sys.stdout, level=logging.INFO)

sample_dict = {
    "name": ["aparna", "pankaj", "sudhir", "Geeku"],
    "degree": ["MBA", "BCA", "M.Tech", "MBA"],
    "score": [90, 40, 80, 98],
}

source_config = PandasSourceConfig(
    dataframe=DataFrame(sample_dict),
    include_columns=["score"],
    text_columns=["name", "degree"],
)
source = PandasSource()

source_response_list = source.lookup(source_config)
for idx, source_response in enumerate(source_response_list):
    logger.info(f"source_response#'{idx}'='{source_response.__dict__}'")
