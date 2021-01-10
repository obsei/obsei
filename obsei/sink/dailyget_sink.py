import logging
from copy import deepcopy
from datetime import timezone
from typing import Any, Dict, List, Optional

import pytz
import requests
from dateutil import parser

from obsei.sink.base_sink import Convertor
from obsei.sink.http_sink import HttpSink, HttpSinkConfig
from obsei.analyzer.text_analyzer import AnalyzerResponse
from obsei.misc.utils import flatten_dict

logger = logging.getLogger(__name__)


TWITTER_URL_PREFIX = "https://twitter.com/"
IST_TZ = pytz.timezone('Asia/Kolkata')


class PayloadConvertor(Convertor):
    def convert(
        self,
        analyzer_response: AnalyzerResponse,
        base_payload: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> Dict[str, Any]:
        request_payload = base_payload or {}

        if analyzer_response.source_name != "Twitter":
            return {**request_payload, **analyzer_response.to_dict()}

        source_information = kwargs["source_information"]

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

        tweet_url = user_url + "/status/" + tweet_id
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
            "Source": source_information,
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


class DailyGetSinkConfig(HttpSinkConfig):
    TYPE: str = "DailyGet"
    partner_id: str
    consumer_phone_number: str
    source_information: str
    headers: Dict[str, Any] = {
        "Content-type": "application/json"
    }


class DailyGetSink(HttpSink):
    def __init__(self, convertor: Convertor = PayloadConvertor(), **data: Any):
        super().__init__(convertor=convertor, **data)

    def send_data(
        self,
        analyzer_responses: List[AnalyzerResponse],
        config: DailyGetSinkConfig,
        **kwargs
    ):
        headers = config.headers

        payloads = []
        responses = []
        for analyzer_response in analyzer_responses:
            payloads.append(self.convertor.convert(
                analyzer_response=analyzer_response,
                base_payload=deepcopy(config.base_payload),
                source_information=config.source_information,
            ))

        for payload in payloads:
            response = requests.post(
                url=config.url,
                json=payload,
                headers=headers,
            )

            logger.info(f"payload='{payload}'")
            logger.info(f"response='{response.__dict__}'")
            responses.append(response)

        return responses
