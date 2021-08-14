from typing import Any, Dict, List, Optional
from urllib import parse

import dateparser
from gnews import GNews
from pydantic import PrivateAttr

from obsei.payload import TextPayload
from obsei.misc.utils import DATETIME_STRING_PATTERN, convert_utc_time
from obsei.source.base_source import BaseSource, BaseSourceConfig
from obsei.source.website_crawler_source import (
    BaseCrawlerConfig,
    TrafilaturaCrawlerConfig,
)


class GoogleNewsConfig(BaseSourceConfig):
    _google_news_client: GNews = PrivateAttr()
    TYPE: str = "GoogleNews"
    query: str
    country: Optional[str] = "US"
    language: Optional[str] = "en"
    max_results: Optional[int] = 100
    lookup_period: Optional[str] = None
    fetch_article: Optional[bool] = False
    crawler_config: Optional[BaseCrawlerConfig] = None

    def __init__(self, **data: Any):
        super().__init__(**data)

        self._google_news_client = GNews(
            language=self.language,
            country=self.country,
            period=self.lookup_period,
            max_results=self.max_results,
        )

        if not self.crawler_config:
            self.crawler_config = TrafilaturaCrawlerConfig(urls=[])

    def get_client(self) -> GNews:
        return self._google_news_client


class GoogleNewsSource(BaseSource):
    NAME: Optional[str] = "GoogleNews"

    def lookup(self, config: GoogleNewsConfig, **kwargs) -> List[TextPayload]:  # type: ignore[override]
        source_responses: List[TextPayload] = []

        # Get data from state
        id: str = kwargs.get("id", None)
        state: Optional[Dict[str, Any]] = (
            None
            if id is None or self.store is None
            else self.store.get_source_state(id)
        )
        update_state: bool = True if id else False
        state = state or dict()
        lookup_period: str = state.get("since_time", config.lookup_period)
        since_time = None if not lookup_period else convert_utc_time(lookup_period)
        last_since_time = since_time

        google_news_client = config.get_client()
        query = parse.quote(config.query, errors='ignore')
        articles = google_news_client.get_news(query)

        for article in articles:
            published_date = (
                None
                if article["published date"] == ""
                else dateparser.parse(article["published date"])
            )

            if config.fetch_article and config.crawler_config:
                extracted_data = config.crawler_config.extract_url(url=article["url"])

                if extracted_data is not None and extracted_data.get("text", None) is not None:
                    article_text = extracted_data["text"]
                    del extracted_data["text"]
                else:
                    article_text = ""

                article["extracted_data"] = extracted_data
            else:
                article_text = article["description"]

            source_responses.append(
                TextPayload(
                    processed_text=f"{article['title']}.\n\n {article_text}",
                    meta=vars(article) if hasattr(article, "__dict__") else article,
                    source_name=self.NAME,
                )
            )

            if published_date and since_time and published_date < since_time:
                break
            if last_since_time is None or (
                published_date and last_since_time < published_date
            ):
                last_since_time = published_date

        if update_state and last_since_time and self.store is not None:
            state["since_time"] = last_since_time.strftime(DATETIME_STRING_PATTERN)
            self.store.update_source_state(workflow_id=id, state=state)

        return source_responses
