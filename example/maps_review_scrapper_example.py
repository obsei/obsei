import logging
import sys

from obsei.source import OSGoogleMapsReviewsSource, OSGoogleMapsReviewsConfig

logger = logging.getLogger(__name__)
logging.basicConfig(stream=sys.stdout, level=logging.INFO)

source_config = OSGoogleMapsReviewsConfig(
    api_key="<Enter Your API Key>", # Get API key from https://outscraper.com/
    queries=[
        "https://www.google.co.in/maps/place/Taj+Mahal/@27.1751496,78.0399535,17z/data=!4m5!3m4!1s0x39747121d702ff6d:0xdd2ae4803f767dde!8m2!3d27.1751448!4d78.0421422"
    ],
    number_of_reviews=3,
)

source = OSGoogleMapsReviewsSource()

source_response_list = source.lookup(source_config)
for source_response in source_response_list:
    logger.info(source_response.__dict__)

