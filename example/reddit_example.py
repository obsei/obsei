import logging
import sys
import time
from datetime import datetime, timedelta

import pytz

from obsei.misc.utils import DATETIME_STRING_PATTERN
from obsei.source.reddit import RedditConfig, RedditSource
from obsei.workflow.store import WorkflowStore
from obsei.workflow.workflow import Workflow, WorkflowConfig


def print_state(id: str):
    logger.info(f'Source State: {source.store.get_source_state(id)}')


logger = logging.getLogger(__name__)
logging.basicConfig(stream=sys.stdout, level=logging.INFO)

since_time = datetime.utcnow().astimezone(pytz.utc) + timedelta(hours=-2)
# Credentials will be fetched from env variable named reddit_client_id and reddit_client_secret
source_config = RedditConfig(
    subreddits=["wallstreetbets"],
    lookup_period=since_time.strftime(DATETIME_STRING_PATTERN)
)

source = RedditSource(store=WorkflowStore())

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

    time.sleep(10)

print_state(workflow.id)
