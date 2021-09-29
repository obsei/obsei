import logging
import sys

from obsei.source import TwitterSourceConfig, TwitterSource, TwitterCredentials

logger = logging.getLogger(__name__)
logging.basicConfig(stream=sys.stdout, level=logging.INFO)

twitter_cred_info = None

# Enter your twitter credentials
# Get it from https://developer.twitter.com/en/apply-for-access
# Currently it will fetch from environment variables: twitter_bearer_token, twitter_consumer_key, twitter_consumer_secret
# Uncomment below lines if you like to pass credentials directly instead of env variables

# twitter_cred_info = TwitterCredentials(
#     bearer_token='<Enter bearer_token>',
#     consumer_key="<Enter consumer_key>",
#     consumer_secret="<Enter consumer_secret>"
# )

source_config = TwitterSourceConfig(
    query="bitcoin",
    lookup_period="1h",
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
    cred_info=twitter_cred_info or None
)

source = TwitterSource()

source_response_list = source.lookup(source_config)
for idx, source_response in enumerate(source_response_list):
    logger.info(f"source_response#'{idx}'='{source_response.__dict__}'")