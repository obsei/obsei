from libs.tiktok.TikTokApi import TikTokApi
import asyncio
from datetime import datetime
import os, sys, pytz
from database import *
from pymongo import MongoClient, UpdateOne


async def get_comments(tiktok_url, count, token, to_date):
    comments = []
    video_arr = tiktok_url.split('/')
    video_id = video_arr[5]
    async with TikTokApi() as api:
        await api.create_sessions(ms_tokens=[token], num_sessions=1, sleep_after=3, headless=False)
        video = api.video(id=video_id)

        async for comment_data in video.comments(count=int(count)):
            comment = comment_data.as_dict
            comment_time = float(comment['create_time'])
            timestamp_datetime = datetime.fromtimestamp(comment_time, pytz.UTC)

            if to_date and timestamp_datetime < to_date or len(comments) == int(count):
                continue

            comment['original_video_url'] = tiktok_url
            comment['original_video_id'] = video_id
            comments.append(comment)
    
    if len(comments) > 0:
        batch_size = 1000
        for i in range(0, len(comments), batch_size):
            bulk_operations = []
            batch = comments[i:i + batch_size]

            for doc in batch:
                bulk_operations.append(
                    UpdateOne(
                        {"cid": doc["cid"]},  
                        {"$set": doc}, 
                        upsert=True,
                    )
                )

            if bulk_operations:
                result = database.tiktok_listeners.bulk_write(bulk_operations)
                print(f"Upserted {result.upserted_count} documents in batch {i // batch_size + 1}.")

    return comments

if __name__ == "__main__":
    ms_token = os.environ.get("ms_token", None)  
    comments_count = 0
    until_datetime_str = None
    video_url = until_datetime = ''

    if len(sys.argv) > 1:
        video_url = sys.argv[1:][0]
        comments_count = sys.argv[1:][1]
        ms_token = os.environ.get("ms_token", sys.argv[1:][2])
        until_datetime_str = sys.argv[1:][3] + ' ' + sys.argv[1:][4] 
    
    if until_datetime_str:
        until_datetime = datetime.strptime(until_datetime_str, "%Y-%m-%d %H:%M:%S").replace(tzinfo=pytz.UTC)
    
    if video_url and ms_token:
        asyncio.run(get_comments(video_url, comments_count, ms_token, until_datetime))
    else:
        print("Missing video_id or ms_token!!!")