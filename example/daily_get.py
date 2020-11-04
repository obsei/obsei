import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional

from datetime import timezone
from dateutil import parser
import pytz

from obsei.sink.base_sink_config import Convertor
from obsei.sink.http_sink_config import HttpSinkConfig
from obsei.sink.http_sink import HttpSink
from obsei.source.twitter_source_config import TwitterSourceConfig
from obsei.source.twitter_source import TwitterSource
from obsei.text_analyzer import AnalyzerResponse, TextAnalyzer
from obsei.utils import flatten_dict

logger = logging.getLogger(__name__)
logging.basicConfig(stream=sys.stdout, level=logging.INFO)

TWITTER_URL_PREFIX = "https://twitter.com/"
IST_TZ = pytz.timezone('Asia/Kolkata')

class PayloadConvertor(Convertor):
    def convert(self, analyzer_response: AnalyzerResponse, base_payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        request_payload = base_payload or {}

        user_url = ""
        positive = 0.0
        negative = 0.0
        text = ""
        tweet_id = None
        created_at_str = None
        classification_list = []

        flat_dict = flatten_dict(analyzer_response.to_dict())
        for k, v in flat_dict.items():
            if "username" in k:
                user_url = TWITTER_URL_PREFIX + v
            elif "text" in k:
                text = str(v).replace("\n", " ")
            elif "positive" in k:
                positive = float(v)
            elif "negative" in k:
                negative = float(v)
            elif "meta_id" in k:
                tweet_id = v
            elif "created_at" in k:
                created_at_str = v
            elif "classification" in k and len(classification_list) < 2:
                classification_list.append(k.rsplit("_", 1)[1])

        if created_at_str:
            created_at = parser.isoparse(created_at_str)
            created_at_str = created_at.replace(
                tzinfo=timezone.utc
            ).astimezone(tz=IST_TZ).strftime('%Y-%m-%d %H:%M:%S')

        tweet_url = user_url + "status/" + tweet_id
        # Sentiment rules
        if negative > 8.0:
            sentiment = "Strong Negative"
        elif 0.3 < negative <= 8.0:
            sentiment = "Negative"
        elif positive >= 0.8:
            sentiment = "Strong Positive"
        elif 0.4 < positive < 0.8:
            sentiment = "Positive"
        else:
            sentiment = "Neutral"

        enquiry = {
            "Source": analyzer_response.source_name + " " + os.environ['DAILYGET_QUERY'],
            "FeedbackBy": user_url,
            "Sentiment": sentiment,
            "TweetUrl": tweet_url,
            "FormattedText": text,
            "PredictedCategories": ",".join(classification_list),
        }

        if created_at_str:
            enquiry["ReportedAt"] = created_at_str

        kv_str_list = [k + ": " + str(v) for k, v in enquiry.items()]
        request_payload["enquiryMessage"] = "\n".join(kv_str_list)
        return request_payload


sink_config = HttpSinkConfig(
    convertor=PayloadConvertor(),
    url=os.environ['DAILYGET_URL'],
    base_payload={
        "partnerId": os.environ['DAILYGET_PARTNER_ID'],
        "consumerPhoneNumber": os.environ['DAILYGET_CONSUMER_NUMBER'],
    },
    payload_mapping={
      "processed_text": ["enquiryMessage"],
      "classification": ["enquiryMessage"],
      "meta": ["enquiryMessage"],
    },
    field_conversion={
        "enquiryMessage": "flat_string"
    }
)

dir_path = Path(__file__).resolve().parent.parent
source_config = TwitterSourceConfig(
    twitter_config_filename=f'{dir_path}/config/twitter.yaml',
    keywords=[os.environ['DAILYGET_QUERY']],
    lookup_period=os.environ['DAILYGET_LOOKUP_PERIOD'],
    tweet_fields=["author_id", "conversation_id", "created_at", "id", "public_metrics", "text"],
    user_fields=["id", "name", "public_metrics", "username", "verified"],
    expansions=["author_id"],
    place_fields=None,
    max_tweets=10,
)

source = TwitterSource()
sink = HttpSink()
text_analyzer = TextAnalyzer(
    classifier_model_name="joeddav/bart-large-mnli-yahoo-answers",
 #   classifier_model_name="joeddav/xlm-roberta-large-xnli",
    initialize_model=True,
)

source_response_list = source.lookup(source_config)
for idx, source_response in enumerate(source_response_list):
    logger.info(f"source_response#'{idx}'='{source_response.__dict__}'")

analyzer_response_list = text_analyzer.analyze_input(
    source_response_list=source_response_list,
    labels=["service", "delay", "tracking", "no response", "missing items", "delivery", "mask"],
    use_sentiment_model=True
)
for idx, an_response in enumerate(analyzer_response_list):
    logger.info(f"analyzer_response#'{idx}'='{an_response.__dict__}'")

sink_response_list = sink.send_data(analyzer_response_list, sink_config)
for sink_response in sink_response_list:
    if sink_response is not None:
        logger.info(f"sink_response='{sink_response.__dict__}'")
