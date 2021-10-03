import logging
import sys

from obsei.analyzer import ZeroShotClassificationAnalyzer, ClassificationAnalyzerConfig
from obsei.sink import SlackSinkConfig, SlackSink
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


sink_config = SlackSinkConfig(
# Uncomment below lines if you like to pass credentials directly instead of env variables
#    slack_token="SLACK_TOKEN",
#    channel_id="CHANNEL_ID",
    jinja_template="""
:bell: Hi there!, a new `<{{payload['meta']['tweet_url']}}|tweet>` of interest is found by *Obsei*
>Tweet Content: 
```{{payload['meta']['text']}}```
>Classifier Data:
```
     {%- for key, value in payload['segmented_data']['classifier_data'].items() recursive%}
         {%- if value is mapping -%}
{{loop(value.items())}}
         {%- else %}
{{key}}: {{value}}
         {%- endif %}
     {%- endfor%}
```
   """
)
sink = SlackSink()

text_analyzer = ZeroShotClassificationAnalyzer(
    model_name_or_path="typeform/mobilebert-uncased-mnli", device="auto"
)

analyzer_config = ClassificationAnalyzerConfig(
    labels=["interface", "slow", "battery"],
    add_positive_negative_labels=False,
)

source_response_list = source.lookup(source_config)
for idx, source_response in enumerate(source_response_list):
    logger.info(f"source_response#'{idx}'='{source_response.__dict__}'")

analyzer_response_list = text_analyzer.analyze_input(
    source_response_list=source_response_list,
    analyzer_config=analyzer_config,
)

for idx, an_response in enumerate(analyzer_response_list):
    logger.info(f"analyzer_response#'{idx}'='{an_response.__dict__}'")

sink_response_list = sink.send_data(
    analyzer_responses=analyzer_response_list, config=sink_config, id=id
)
for idx, sink_response in enumerate(sink_response_list):
    logger.info(f"source_response#'{idx}'='{sink_response.__dict__}'")
