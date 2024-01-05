from libs.tiktok.TikTokApi import TikTokApi
import asyncio
import os, sys
from database import *

import datetime


async def search_videos(keyword, max, token, config_id):
    async with TikTokApi() as api:
        await api.create_sessions(
            ms_tokens=[token],
            num_sessions=1,
            sleep_after=3,
            headless=False)
        array = []
        async for video_url in api.search.videos(keyword, count=int(max)):
            array.append({
                'generated_config_id': ObjectId(config_id), 
                'url': video_url, 
                'keyword': keyword, 
                'created_at': datetime.datetime.now()
                })

        database.urls.insert_many(array)


if __name__ == "__main__":
    ms_token = os.environ.get("ms_token", None)
    max_videos = 0
    keywords = config_id = ''

    if len(sys.argv) > 1:
        keywords = sys.argv[1:][0]
        ms_token = os.environ.get("ms_token", sys.argv[1:][1])
        max_videos = sys.argv[1:][2]
        config_id = sys.argv[1:][3]

    if keywords and ms_token and max_videos:
        asyncio.run(search_videos(keywords, max_videos, ms_token, config_id))
    else:
        print("Missing keywords or max_videos or ms_token!!!")
