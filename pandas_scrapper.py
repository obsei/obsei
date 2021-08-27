from obsei.source.pandas_source import (
    PandasSourceConfig,
    PandasSourceScrapper,
)
import logging
import sys
path = "glass1.csv"


logger = logging.getLogger(__name__)
logging.basicConfig(stream=sys.stdout,level=logging.INFO)

source_config = PandasSourceConfig(
    target = path,
    input_type = "csv",
    columns = ["fe","type"]
)
source = PandasSourceScrapper()
source_response_list = source.lookup(source_config)
for idx, source_response in enumerate(source_response_list):
    logger.info(f"source_response#'{idx}'='{source_response.__dict__}'")