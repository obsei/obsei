import logging
import sys
import time

from obsei.workflow.store import WorkflowStore
from obsei.source.twitter_source import TwitterSource, TwitterSourceConfig
from obsei.workflow.workflow import Workflow, WorkflowConfig

logger = logging.getLogger(__name__)
logging.basicConfig(stream=sys.stdout, level=logging.INFO)

source = TwitterSource(store=WorkflowStore())


def print_state(id: str):
    logger.info(f'Source State: {source.store.get_source_state(id)}')


source_config = TwitterSourceConfig(
    keywords=["india"],
    lookup_period="2m",
    tweet_fields=["author_id", "conversation_id", "created_at", "id", "public_metrics", "text"],
    user_fields=["id", "name", "public_metrics", "username", "verified"],
    expansions=["author_id"],
    place_fields=None,
    max_tweets=10,
)

# This example also
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

    time.sleep(180)

print_state(workflow.id)
