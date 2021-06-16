import json
import logging
from abc import abstractmethod
from typing import List, Optional

import mmh3
from trafilatura import extract, feeds, fetch_url, sitemaps

from obsei.payload import TextPayload
from obsei.source.base_source import BaseSource, BaseSourceConfig

logger = logging.getLogger(__name__)


class BaseCrawlerConfig(BaseSourceConfig):
    TYPE: str = "BaseCrawler"

    @abstractmethod
    def extract_url(self, url: str, url_id: str = None):
        pass

    @abstractmethod
    def find_urls(self, url: str):
        pass


class TrafilaturaCrawlerConfig(BaseCrawlerConfig):
    # To understand about these configuration params refer:
    # https://trafilatura.readthedocs.io/
    _output_format: str = "json"
    TYPE: str = "Crawler"
    urls: List[str]
    include_comments: bool = False
    include_tables: bool = True
    no_fallback: bool = False
    include_images: bool = False
    include_formatting: bool = False
    deduplicate: bool = True
    no_ssl: bool = False
    is_feed: bool = False
    is_sitemap: bool = False
    include_links: bool = True
    target_language: Optional[str] = None
    url_blacklist: Optional[List[str]] = None

    def extract_url(self, url: str, url_id: str = None):
        url_id = url_id or "{:02x}".format(mmh3.hash(url, signed=False))
        url_content = fetch_url(
            url=url,
            no_ssl=self.no_ssl,
        )
        extracted_dict = None
        if url_content is not None:
            extracted_data = extract(
                filecontent=url_content,
                record_id=url_id,
                no_fallback=self.no_fallback,
                output_format=self._output_format,
                include_comments=self.include_comments,
                include_tables=self.include_tables,
                include_images=self.include_images,
                include_formatting=self.include_formatting,
                include_links=self.include_links,
                deduplicate=self.deduplicate,
                url_blacklist=self.url_blacklist,
                target_language=self.target_language,
            )

            if extracted_data:
                extracted_dict = json.loads(extracted_data)
                if "raw-text" in extracted_dict:
                    del extracted_dict["raw-text"]

        return extracted_dict

    def find_urls(self, url: str):
        urls: List[str] = []
        if self.is_sitemap:
            urls = sitemaps.sitemap_search(url=url, target_lang=self.target_language)
        elif self.is_feed:
            urls = feeds.find_feed_urls(url=url, target_lang=self.target_language)

        return urls


class TrafilaturaCrawlerSource(BaseSource):
    NAME: Optional[str] = "Crawler"

    def lookup(  # type: ignore[override]
        self, config: TrafilaturaCrawlerConfig, **kwargs
    ) -> List[TextPayload]:
        source_responses: List[TextPayload] = []

        final_urls = []
        if config.is_sitemap or config.is_feed:
            for url in config.urls:
                final_urls.extend(config.find_urls(url=url))
        else:
            final_urls = config.urls

        for url in final_urls:
            extracted_data = config.extract_url(url=url)
            if extracted_data is None:
                logger.warning(f"Unable to crawl {url}, hence skipping it")
                continue
            comments = (
                "" if "comments" not in extracted_data else extracted_data["comments"]
            )
            source_responses.append(
                TextPayload(
                    processed_text=f"{extracted_data['text']}. {comments}",
                    meta=extracted_data,
                    source_name=self.NAME,
                )
            )

        return source_responses
