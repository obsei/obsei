from pydantic import BaseModel

from pytok.tiktok import PyTok

import datetime
import pytz

from typing import Optional, Any, List, Dict, Generator


class TiktokCommentsScrapper(BaseModel):
    video_url: Optional[str] = None
    max_comments: Optional[int] = 20

    def __init__(self, **kwargs: Any):
        super().__init__(**kwargs)

    async def fetch_tiktok_comments(self, until_datetime=None):
        comments = []
        video = self.video_url

        async with PyTok(headless=False) as api:
            async for comment in api.video(url=video).comments(count=1000):
                comment_time: Optional[float] = float(comment['create_time'])
                timestamp_datetime = datetime.datetime.fromtimestamp(comment_time, pytz.UTC)

                if timestamp_datetime < until_datetime or len(comments) == self.max_comments:
                    continue

                comment['comment_url'] = comment['share_info']['url']
                comment['nickname'] = comment['user']['nickname']
                comment['uid'] = comment['user']['uid']
                comment['unique_id'] = comment['user']['unique_id']

                del comment['share_info']
                del comment['user']

                comments.append(comment)

        return comments
