import logging
import sys

from obsei.source.facebook_source import FacebookSource, FacebookSourceConfig

logger = logging.getLogger(__name__)
logging.basicConfig(stream=sys.stdout, level=logging.INFO)

source_config = FacebookSourceConfig(page_id="110844591144719")
source = FacebookSource()
source_response_list = source.lookup(source_config)

logger.info("DETAILS:")
for source_response in source_response_list:
    logger.info(source_response)

logger.info("TEXT:")
for source_response in source_response_list:
    logger.info(source_response.processed_text)
