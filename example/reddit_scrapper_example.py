import logging
import sys
from datetime import datetime, timedelta

import pytz

from obsei.misc.utils import DATETIME_STRING_PATTERN
from obsei.source.reddit_scrapper import RedditScrapperConfig, RedditScrapperSource


def print_state(id: str):
    logger.info(f"Source State: {source.store.get_source_state(id)}")


logger = logging.getLogger(__name__)
logging.basicConfig(stream=sys.stdout, level=logging.INFO)

since_time = datetime.utcnow().astimezone(pytz.utc) + timedelta(days=-1)

source_config = RedditScrapperConfig(
    url="https://www.reddit.com/r/wallstreetbets/comments/.rss?sort=new",
    user_agent="testscript by u/FitStatistician7378",
    lookup_period=since_time.strftime(DATETIME_STRING_PATTERN),
)

source = RedditScrapperSource()

source_response_list = source.lookup(source_config)
for source_response in source_response_list:
    logger.info(source_response.__dict__)
