import logging
import sys

from obsei.source.google_place_reviews import (
    GooglePlaceConfig,
    GooglePlaceSource
)

logger = logging.getLogger(__name__)
logging.basicConfig(stream=sys.stdout, level=logging.INFO)

source_config = GooglePlaceConfig(place_id='', api_key='AIzaasdf')
source = GooglePlaceSource()

source_response_list = source.lookup(source_config)
for idx, source_response in enumerate(source_response_list):
    logger.info(f"source_response#'{idx}'='{source_response.__dict__}'")
