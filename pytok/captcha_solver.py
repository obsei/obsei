import asyncio
import random
from urllib.parse import urlparse

import cv2
import base64
import numpy as np
import requests


class CaptchaSolver:
    def __init__(self, response, puzzle, piece):
        self._request = response.request
        self._response = response
        self._client = requests.Session()
        self._puzzle = base64.b64encode(puzzle)
        self._piece = base64.b64encode(piece)

    def _host(self):
        return urlparse(self._request.url).netloc

    def _params(self):
        return urlparse(self._request.url).query

    def _headers(self) -> dict:
        return self._request.headers

    async def _get_challenge(self) -> dict:
        return await self._response.json()

    async def _solve_captcha(self) -> dict:
        solver = PuzzleSolver(self._puzzle, self._piece)
        maxloc = solver.get_position()
        randlength = round(
            random.random() * (100 - 50) + 50
        )
        await asyncio.sleep(1)  # don't remove delay or it will fail
        return {
            "maxloc": maxloc,
            "randlenght": randlength
        }

    def _post_captcha(self, solve: dict) -> dict:
        params = self._params()

        body = {
            "modified_img_width": 552,
            "id": solve["id"],
            "mode": "slide",
            "reply": list(
                {
                    "relative_time": i * solve["randlenght"],
                    "x": round(
                        solve["maxloc"] / (solve["randlenght"] / (i + 1))
                    ),
                    "y": solve["tip"],
                }
                for i in range(
                    solve["randlenght"]
                )
            ),
        }

        host = self._host()
        headers = self._headers()

        resp = self._client.post(
            url=(
                    "https://"
                    + host
                    + "/captcha/verify?"
                    + params
            ),
            headers=headers.update(
                {
                    "content-type": "application/json"
                }
            ),
            json=body
        )

        if resp.status_code != 200:
            raise Exception("Captcha was not solved")

        return resp.json()

    async def solve_captcha(self):
        captcha_challenge = await self._get_challenge()

        captcha_id = captcha_challenge["data"]["id"]
        tip_y = captcha_challenge["data"]["question"]["tip_y"]

        solve = await self._solve_captcha()

        solve.update(
            {
                "id": captcha_id,
                "tip": tip_y
            }
        )

        return self._post_captcha(solve)


class PuzzleSolver:
    def __init__(self, base64puzzle, base64piece):
        self.puzzle = base64puzzle
        self.piece = base64piece

    def get_position(self):
        puzzle = self.__background_preprocessing()
        piece = self.__piece_preprocessing()
        matched = cv2.matchTemplate(
            puzzle,
            piece,
            cv2.TM_CCOEFF_NORMED
        )
        min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(matched)
        return max_loc[0]

    def __background_preprocessing(self):
        img = self.__img_to_grayscale(self.piece)
        background = self.__sobel_operator(img)
        return background

    def __piece_preprocessing(self):
        img = self.__img_to_grayscale(self.puzzle)
        template = self.__sobel_operator(img)
        return template

    def __sobel_operator(self, img):
        scale = 1
        delta = 0
        ddepth = cv2.CV_16S

        img = cv2.GaussianBlur(img, (3, 3), 0)
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        grad_x = cv2.Sobel(
            gray,
            ddepth,
            1,
            0,
            ksize=3,
            scale=scale,
            delta=delta,
            borderType=cv2.BORDER_DEFAULT,
        )
        grad_y = cv2.Sobel(
            gray,
            ddepth,
            0,
            1,
            ksize=3,
            scale=scale,
            delta=delta,
            borderType=cv2.BORDER_DEFAULT,
        )
        abs_grad_x = cv2.convertScaleAbs(grad_x)
        abs_grad_y = cv2.convertScaleAbs(grad_y)
        grad = cv2.addWeighted(abs_grad_x, 0.5, abs_grad_y, 0.5, 0)

        return grad

    def __img_to_grayscale(self, img):
        return cv2.imdecode(
            self.__string_to_image(img),
            cv2.IMREAD_COLOR
        )

    def __string_to_image(self, base64_string):
        return np.frombuffer(
            base64.b64decode(base64_string),
            dtype="uint8"
        )
