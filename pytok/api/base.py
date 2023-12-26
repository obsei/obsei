import asyncio
import random

from playwright.async_api import expect

from .. import exceptions, captcha_solver

TOK_DELAY = 30
CAPTCHA_DELAY = 999999

LOGIN_CLOSE_LOCATOR = "css=[data-e2e=modal-close-inner-button]"

def get_captcha_element(page):
    return page.locator('Rotate the shapes') \
        .or_(page.get_by_text('Verify to continue:', exact=True)) \
        .or_(page.get_by_text('Click on the shapes with the same size', exact=True))

class Base:

    async def check_initial_call(self, url):
        async with self.wait_for_requests(url) as event:
            response = await event.value.response()
            if response.status >= 300:
                raise exceptions.NotAvailableException("Content is not available")

    async def wait_for_content_or_captcha(self, content_tag):
        page = self.parent._page

        content_element = page.locator(content_tag).first
        # content_element = page.get_by_text('Videos', exact=True)
        captcha_element = get_captcha_element(page)

        try:
            await expect(content_element.or_(captcha_element)).to_be_visible(timeout=TOK_DELAY * 1000)
            
        except TimeoutError as e:
            raise exceptions.TimeoutException(str(e))

        captcha_visible = await captcha_element.is_visible()
        if captcha_visible:
            await self.solve_captcha()
            await expect(content_element).to_be_visible(timeout=TOK_DELAY * 1000)

        return content_element

    async def wait_for_content_or_unavailable_or_captcha(self, content_tag, unavailable_text):
        page = self.parent._page
        content_element = page.locator(content_tag).first
        captcha_element = get_captcha_element(page)
        unavailable_element = page.get_by_text(unavailable_text, exact=True)
        try:
            await expect(content_element.or_(captcha_element).or_(unavailable_element)).to_be_visible(timeout=TOK_DELAY * 1000)
        except TimeoutError as e:
            raise exceptions.TimeoutException(str(e))

        if await captcha_element.is_visible():
            await self.solve_captcha()
            await expect(content_element.or_(unavailable_element)).to_be_visible(timeout=TOK_DELAY * 1000)

        if await unavailable_element.is_visible():
            raise exceptions.NotAvailableException(f"Content is not available with message: '{unavailable_text}'")

        return content_element

    async def check_for_unavailable_or_captcha(self, unavailable_text):
        page = self.parent._page
        captcha_element = get_captcha_element(page)
        unavailable_element = page.get_by_text(unavailable_text, exact=True)

        captcha_visible = await captcha_element.is_visible()
        if captcha_visible:
            await self.solve_captcha()

        login_element = page.get_by_text('Log in to TikTok', exact=True)
        login_visible = await login_element.is_visible()
        if login_visible:
            await page.click(LOGIN_CLOSE_LOCATOR)

        if await unavailable_element.is_visible():
            raise exceptions.NotAvailableException(f"Content is not available with message: '{unavailable_text}'")


    def wait_for_requests(self, api_path, timeout=TOK_DELAY):
        page = self.parent._page
        try:
            return page.expect_request(api_path, timeout=timeout * 1000)
        except TimeoutError as e:
            raise exceptions.TimeoutException(str(e))

    def get_requests(self, api_path):
        return [request for request in self.parent._requests if api_path in request.url]
    
    def get_responses(self, api_path):
        return [response for response in self.parent._responses if api_path in response.url]

    async def get_response_body(self, response):
        return await response.body()

    async def scroll_to_bottom(self, speed=4):
        page = self.parent._page
        current_scroll_position = await page.evaluate("() => document.documentElement.scrollTop || document.body.scrollTop;")
        new_height = current_scroll_position + 1
        while current_scroll_position <= new_height:
            current_scroll_position += speed + random.randint(-speed, speed)
            await page.evaluate(f"() => window.scrollTo(0, {current_scroll_position});")
            new_height = await page.evaluate("() => document.body.scrollHeight;")

    async def scroll_to(self, position, speed=5):
        page = self.parent._page
        current_scroll_position = await page.evaluate("() => document.documentElement.scrollTop || document.body.scrollTop;")
        new_height = current_scroll_position + 1
        while current_scroll_position <= new_height:
            current_scroll_position += speed + random.randint(-speed, speed)
            await page.evaluate(f"() => window.scrollTo(0, {current_scroll_position});")
            new_height = await page.evaluate("() => document.body.scrollHeight;")
            if current_scroll_position > position:
                break

    async def slight_scroll_up(self, speed=4):
        page = self.parent._page
        desired_scroll = -500
        current_scroll = 0
        while current_scroll > desired_scroll:
            current_scroll -= speed + random.randint(-speed, speed)
            await page.evaluate(f"() => window.scrollBy(0, {-speed});")

    async def wait_until_not_skeleton_or_captcha(self, skeleton_tag):
        page = self.parent._page
        content = page.locator(f'[data-e2e={skeleton_tag}]')
        try:
            await expect(content).not_to_be_visible()
        except TimeoutError as e:
            captcha_element = get_captcha_element(page)
            if await captcha_element.is_visible():
                await self.solve_captcha()
            else:
                raise exceptions.TimeoutException(str(e))

    async def check_and_wait_for_captcha(self):
        page = self.parent._page
        captcha_element = get_captcha_element(page)
        captcha_visible = await captcha_element.is_visible()
        if captcha_visible:
            await self.solve_captcha()

    async def check_and_close_signin(self):
        page = self.parent._page
        signin_visible = await page.get_by_text('Sign in', exact=True).is_visible()
        if signin_visible:
            await page.click(LOGIN_CLOSE_LOCATOR)
                
    async def solve_captcha(self):
        request = self.get_requests('/captcha/get')[0]
        captcha_response = await request.response()
        captcha_json = await captcha_response.json()
        captcha_type = captcha_json['data']['mode']
        if captcha_type != 'slide':
            raise exceptions.CaptchaException(f"Unsupported captcha type: {captcha_type}")
        
        puzzle_req = self.get_requests(captcha_json['data']['question']['url1'])[0]
        puzzle_response = await puzzle_req.response()
        puzzle = await puzzle_response.body()

        if not puzzle:
            raise exceptions.CaptchaException("Puzzle was not found in response")

        piece_req = self.get_requests(captcha_json['data']['question']['url2'])[0]
        piece_response = await piece_req.response()
        piece = await piece_response.body()

        if not piece:
            raise exceptions.CaptchaException("Piece was not found in response")

        await captcha_solver.CaptchaSolver(captcha_response, puzzle, piece).solve_captcha()

        await asyncio.sleep(1)
        page = self.parent._page
        await page.reload()
        captcha_element = page.get_by_text('Verify to continue:', exact=True)
        await expect(captcha_element).not_to_be_visible()

