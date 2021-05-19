import logging
import sys
import time
from datetime import datetime, timedelta

import pytz

from obsei.misc.utils import DATETIME_STRING_PATTERN
from obsei.source.reddit_scrapper import RedditScrapperConfig, RedditScrapperSource
from obsei.workflow.store import WorkflowStore
from obsei.workflow.workflow import Workflow, WorkflowConfig


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

source = RedditScrapperSource(store=WorkflowStore())

workflow = Workflow(
    config=WorkflowConfig(
        source_config=source_config,
    ),
)
source.store.add_workflow(workflow)


for i in range(1, 4):
    print_state(workflow.id)
    source_response_list = source.lookup(source_config, id=workflow.id)

    if source_response_list is None or len(source_response_list) == 0:
        break

    for source_response in source_response_list:
        logger.info(source_response.__dict__)

    time.sleep(30)

print_state(workflow.id)
