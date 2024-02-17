from libs.tiktok.TikTokApi import TikTokApi
import asyncio
import os

async def search_users():
    async with TikTokApi() as api:
        await api.create_sessions(
            ms_tokens=['fOKaVGcLVaHb09QJ15aVjncVQ7iMumi6tEcKvqstrVAIMFAIVsoBiP3Jrmc7Hw10fNztwxtZw_A9jwJ6vUf7QTYI2wey9DCt0FEy_qPSOQ-0MaXtxm6KbzAA3GwL4-vJTzV6Sws3dsgRzdjB'],
            num_sessions=1,
            sleep_after=3,
            headless=False)
        async for user in api.search.users("david teather", count=10):
            print(user)

        async for video in api.search.videos("david teather", count=10):
            print(video)


if __name__ == "__main__":
    asyncio.run(search_users())
