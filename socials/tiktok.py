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

# import asyncio
#
# from playwright.async_api import async_playwright
#
# from socials import captcha_solver
# from socials.captcha_solver import CaptchaSolver
#
#
# async def main(self):
#     async with async_playwright() as p:
#         browser = await p.chromium.launch()
#         page = await browser.new_page()
#         await page.goto("https://www.tiktok.com/@hutrajshrestha/video/7285994508431559937/")
#
#         print(await page.title(),111111111)
#
#         await page.screenshot(path="screenshot.png")
#
#         self.wait_until_not_skeleton_or_captcha('video-skeleton-container')
#
#         await browser.close()
#
#
# async def solve_captcha(self):
#     request = self.get_requests('/captcha/get')[0]
#     captcha_response = await request.response()
#     captcha_json = await captcha_response.json()
#     captcha_type = captcha_json['data']['mode']
#     if captcha_type != 'slide':
#         raise exceptions.CaptchaException(f"Unsupported captcha type: {captcha_type}")
#
#     puzzle_req = self.get_requests(captcha_json['data']['question']['url1'])[0]
#     puzzle_response = await puzzle_req.response()
#     puzzle = await puzzle_response.body()
#
#     if not puzzle:
#         raise exceptions.CaptchaException("Puzzle was not found in response")
#
#     piece_req = self.get_requests(captcha_json['data']['question']['url2'])[0]
#     piece_response = await piece_req.response()
#     piece = await piece_response.body()
#
#     if not piece:
#         raise exceptions.CaptchaException("Piece was not found in response")
#
#     await captcha_solver.CaptchaSolver(captcha_response, puzzle, piece).solve_captcha()
#
#     await asyncio.sleep(1)
#     page = self.parent._page
#     await page.reload()
#     captcha_element = page.get_by_text('Verify to continue:', exact=True)
#     await expect(captcha_element).not_to_be_visible()
# asyncio.run(main())
#
# # import asyncio
# # from playwright.async_api import async_playwright, Playwright
# #
# # async def run(playwright: Playwright):
# #     firefox = playwright.firefox
# #     browser = await firefox.launch()
# #     page = await browser.new_page()
# #     await page.goto("https://example.com")
# #     # await browser.close()
# #
# # async def main():
# #     async with async_playwright() as playwright:
# #         await run(playwright)
# # asyncio.run(main())
