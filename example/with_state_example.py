import logging
import sys
import time

from obsei.workflow.store import WorkflowStore
from obsei.source.twitter_source import TwitterSource, TwitterSourceConfig
from obsei.workflow.workflow import Workflow, WorkflowConfig

logger = logging.getLogger(__name__)
logging.basicConfig(stream=sys.stdout, level=logging.INFO)

# Create workflow store instance, by default it will use SQLite to store state data
store = WorkflowStore()

# Pass store reference to observer, so it can use it to store state data
source = TwitterSource(store=store)


def print_state(id: str):
    logger.info(f"Source State: {source.store.get_source_state(id)}")


source_config = TwitterSourceConfig(
    keywords=["india"],
    lookup_period="2m",
    tweet_fields=[
        "author_id",
        "conversation_id",
        "created_at",
        "id",
        "public_metrics",
        "text",
    ],
    user_fields=["id", "name", "public_metrics", "username", "verified"],
    expansions=["author_id"],
    place_fields=None,
    max_tweets=10,
)

# Create instance of workflow, adding observer config to it, it will autgenerate unique workflow id
workflow = Workflow(
    config=WorkflowConfig(
        source_config=source_config,
    ),
)
# Insert workflow config to DB store
store.add_workflow(workflow)

for i in range(1, 4):
    print_state(workflow.id)
    # Now always pass workflow id to lookup function
    # Observer will fetch old data from DB suing this id and later store new updated state data against this id to DB
    source_response_list = source.lookup(source_config, id=workflow.id)

    if source_response_list is None or len(source_response_list) == 0:
        break

    time.sleep(180)

print_state(workflow.id)
