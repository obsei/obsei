from libs.tiktok.TikTokApi import TikTokApi
import asyncio, os, sys, datetime
from bson import ObjectId
from database import *
from pymongo import ReplaceOne


async def search_videos(keyword, max, token, config_id):
    async with TikTokApi() as api:
        await api.create_sessions(
            ms_tokens=[token],
            num_sessions=1,
            sleep_after=3,
            headless=False)
        array = []
        async for video_url in api.search.videos(keyword, count=int(max)):
            if len(array) == max:
                break

            array.append({
                'generated_config_id': ObjectId(config_id),
                'url': video_url,
                'keyword': keyword,
                'created_at': datetime.datetime.now()
            })

        update_operations = [
            ReplaceOne({'url': doc['url']}, doc, upsert=True)
            for doc in array
        ]

        # Perform the upsert operations
        result = database.urls.bulk_write(update_operations)

        # Print the upsert result
        print(f"{result.upserted_count} documents were inserted, {result.modified_count} documents were updated.")


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
