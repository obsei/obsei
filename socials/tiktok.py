import asyncio
import json

from pytok.tiktok import PyTok

videos = [
    {
        'id': '7285994508431559937',
        'author': {
            'uniqueId': 'hutrajshrestha'
        }
    }
]


async def main():
    async with PyTok(headless=False) as api:
        for video in videos:
            comments = []
            async for comment in api.video(id=video['id'], username=video['author']['uniqueId']).comments(count=1000):
                comments.append(comment)

            print(comments, 11111)
            # with open("out.json", "w") as f:
            #     json.dump(comments, f)


if __name__ == "__main__":
    asyncio.run(main())
