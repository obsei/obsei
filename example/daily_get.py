from socialtracker.sink.http_sink_config import HttpSinkConfig
from socialtracker.sink.http_sink import HttpSink
from socialtracker.source.twitter_source_config import TwitterSourceConfig
from socialtracker.source.twitter_source import TwitterSource
from socialtracker.text_analyzer import TextAnalyzer

sink_config = HttpSinkConfig(
    url=<URL>,
    base_payload={
        "partnerId": <PARTNER_ID>,
    },
    payload_mapping={
      "text": ["enquiryMessage", "text"],
      "sentiment_value": ["enquiryMessage", "sentiment_value"],
      "sentiment_type": ["enquiryMessage", "sentiment_type"],
      "classification_map": ["enquiryMessage", "classification_map"],
      "meta_information": ["enquiryMessage", "meta_information"],
    }
)

source_config = TwitterSourceConfig(
    consumer_key="",
    consumer_secret="",
    query="XpressBees",
    lookup_period="15d",
)

source = TwitterSource()
sink = HttpSink()
text_analyzer = TextAnalyzer(
    initialize_sentiment_model=False,
)

source_response_list = source.lookup(source_config)
print("source_response_list=", source_response_list)
analyzer_response_list = text_analyzer.analyze_input(
    source_response_list
)
print("analyzer_response_list=", analyzer_response_list)
sink_response_list = sink.send_data(analyzer_response_list, sink_config)
print("sink_response_list=", sink_response_list)
