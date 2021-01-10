import logging
from datetime import datetime
from time import mktime
from typing import Any, List, Optional

import feedparser
import requests
from feedparser import FeedParserDict
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class Review(BaseModel):
    version: str
    rating: int
    id: int
    title: str
    content: str
    date: datetime
    author_link: str
    author_name: str
    country: str
    vote_count: Optional[int] = 0
    vote_sum: Optional[int] = 0


class AppStoreReviewsReader(BaseModel):
    _base_rss_url: str = "https://itunes.apple.com/{country}/rss/customerreviews/id={app_id}/xml"
    country: str
    app_id: Optional[str] = None

    def __init__(self, **data: Any):
        super().__init__(**data)

    def fetch_reviews(self, after: Optional[datetime] = None, since_id: Optional[int] = None) -> List[Review]:
        feed_url = self._base_rss_url.format(country=self.country, app_id=self.app_id)
        has_next: bool = True
        reviews: List[Review] = []
        while has_next:
            has_next = False
            feed = self.fetch_feed(feed_url)

            if feed.feed.links is not None:
                for link in feed.feed.links:
                    if link.get('rel', '') == 'next':
                        feed_url = link.href
                        has_next = True
                        break

            for entry in feed.entries:
                if after is not None and after.timetuple() > entry.updated_parsed:
                    has_next = False
                    break

                if since_id is not None and since_id >= int(entry.id):
                    has_next = False
                    break

                try:
                    reviews.append(
                        Review(
                            country=self.country,
                            version=entry.im_version,
                            rating=int(entry.im_rating),
                            id=int(entry.id),
                            title=entry.title,
                            content=entry.summary,
                            date=datetime.fromtimestamp(mktime(entry.updated_parsed)),
                            vote_count=int(entry.im_votecount),
                            vote_sum=int(entry.im_votesum),
                            author_name=entry.author_detail.name,
                            author_link=str(entry.author_detail.href)
                        )
                    )
                except Exception:
                    logger.error(f'Error parsing review={entry}')

        return reviews

    @staticmethod
    def fetch_feed(feed_url: str) -> FeedParserDict:
        # On MacOS https do not work, hence using workaround
        # Refer https://github.com/uvacw/inca/issues/162
        is_https = "https://" in feed_url[:len("https://")]
        if is_https:
            feed_content = requests.get(feed_url)
            feed = feedparser.parse(feed_content.text)
        else:
            feed = feedparser.parse(feed_url)

        return feed
