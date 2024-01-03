from pydantic import BaseModel

import datetime
import pytz
from pytiktok.TikTokApi import TikTokApi
from typing import Optional, Any, List, Dict, Generator
import os
import subprocess

class TiktokCommentsScrapper(BaseModel):
    ms_token: Optional[str] = None
    video_url: Optional[str] = None
    max_comments: Optional[int] = 20

    def __init__(self, **kwargs: Any):
        super().__init__(**kwargs)

    async def fetch_tiktok_comments(self, until_datetime=None):
        try:
            command = "xvfb-run -a python3 pytiktok/process_tiktok.py " +  self.video_url + " " + str(self.max_comments) + " " + str(self.ms_token) + " " + str(until_datetime.strftime("%Y-%m-%d %H:%M:%S"))
            output = subprocess.run(command,  shell=True, stderr=subprocess.STDOUT)
        except subprocess.CalledProcessError as e:
            print(f"Command failed with error: {e.output.decode('utf-8').strip()}")
            return False;

        return True;

        # comments = []
      
        # async with TikTokApi() as api:
        #     await api.create_sessions(ms_tokens=[ms_token], num_sessions=1, sleep_after=3, headless=False)
        #     video = api.video(id=video_id)
        #     count = 0
        #     async for comment_data in video.comments(count=30):
        #         comment = comment_data.as_dict
        #         comment_time: Optional[float] = float(comment['create_time'])
        #         timestamp_datetime = datetime.datetime.fromtimestamp(comment_time, pytz.UTC)

        #         if timestamp_datetime < until_datetime or len(comments) == self.max_comments:
        #             continue

        #         comment['comment_url'] = comment['share_info']['url']
        #         comment['nickname'] = comment['user']['nickname']
        #         comment['uid'] = comment['user']['uid']
        #         comment['unique_id'] = comment['user']['unique_id']

        #         del comment['share_info']
        #         del comment['user']

        #         comments.append(comment)
        
        # print(comments,'===============================================')

        # return comments
