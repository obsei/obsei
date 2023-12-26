from __future__ import annotations
import logging

from urllib.parse import urlencode
from ..exceptions import *
import re
import json
import time

from typing import TYPE_CHECKING, ClassVar, Iterator, Optional

import requests

if TYPE_CHECKING:
    from ..tiktok import PyTok
    from .video import Video

from .base import Base


class Hashtag(Base):
    """
    A TikTok Hashtag/Challenge.

    Example Usage
    ```py
    hashtag = api.hashtag(name='funny')
    ```
    """

    parent: ClassVar[PyTok]

    id: Optional[str]
    """The ID of the hashtag"""
    name: Optional[str]
    """The name of the hashtag (omiting the #)"""
    as_dict: dict
    """The raw data associated with this hashtag."""

    def __init__(
        self,
        name: Optional[str] = None,
        id: Optional[str] = None,
        data: Optional[dict] = None,
    ):
        """
        You must provide the name or id of the hashtag.
        """
        self.name = name
        self.id = id

        if data is not None:
            self.as_dict = data
            self.__extract_from_data()

    def info(self, **kwargs) -> dict:
        """
        Returns TikTok's dictionary representation of the hashtag object.
        """
        raise NotImplementedError()

    def info_full(self, **kwargs) -> dict:
        """
        Returns all information sent by TikTok related to this hashtag.

        Example Usage
        ```py
        hashtag_data = api.hashtag(name='funny').info_full()
        ```
        """
        raise NotImplementedError()

    async def videos(self, count=30, offset=0, **kwargs) -> Iterator[Video]:
        """Returns a dictionary listing TikToks with a specific hashtag.

        - Parameters:
            - count (int): The amount of videos you want returned.
            - offset (int): The the offset of videos from 0 you want to get.

        Example Usage
        ```py
        for video in api.hashtag(name='funny').videos():
            # do something
        ```
        """
        page = self.parent._page

        url = f"https://www.tiktok.com/tag/{self.name}"
        await page.goto(url)

        self.wait_for_content_or_captcha('challenge-item')

        processed_urls = []
        amount_yielded = 0
        pull_method = 'browser'
        tries = 0
        MAX_TRIES = 5

        data_request_path = "api/challenge/item_list"

        while amount_yielded < count:
            self.parent.request_delay()

            if pull_method == 'browser':
                search_requests = self.get_requests(data_request_path)
                search_requests = [request for request in search_requests if request.url not in processed_urls]
                for request in search_requests:
                    processed_urls.append(request.url)
                    body = self.get_response_body(request)
                    res = json.loads(body)
                    if res.get('type') == 'verify':
                        # this is the captcha denied response
                        continue

                    videos = res.get("itemList", [])
                    amount_yielded += len(videos)
                    for video in videos:
                        yield self.parent.video(data=video)

                    if not res.get("hasMore", False):
                        self.parent.logger.info(
                            "TikTok isn't sending more TikToks beyond this point."
                        )
                        return

                for _ in range(tries):
                    self.slight_scroll_up()
                    self.scroll_to_bottom()
                    self.parent.request_delay()
                try:
                    self.wait_for_requests(data_request_path, timeout=tries*4)
                except TimeoutException:
                    tries += 1
                    if tries > MAX_TRIES:
                        raise
                    continue

            elif pull_method == 'requests':
                cursor = res["cursor"]
                next_url = re.sub("cursor=([0-9]+)", f"cursor={cursor}", request.url)

                r = requests.get(next_url, headers=request.headers)
                try:
                    res = r.json()
                except json.decoder.JSONDecodeError:
                    continue

                if res.get('type') == 'verify':
                    self.check_and_wait_for_captcha()

                videos = res.get("itemList", [])

                amount_yielded += len(videos)
                for video in videos:
                    yield self.parent.video(data=video)

                if not res.get("hasMore", False):
                    self.parent.logger.info(
                        "TikTok isn't sending more TikToks beyond this point."
                    )
                    return

    def __extract_from_data(self):
        data = self.as_dict
        keys = data.keys()

        if "title" in keys:
            self.id = data["id"]
            self.name = data["title"]

        if None in (self.name, self.id):
            Hashtag.parent.logger.error(
                f"Failed to create Hashtag with data: {data}\nwhich has keys {data.keys()}"
            )

    def __repr__(self):
        return self.__str__()

    def __str__(self):
        return f"PyTok.hashtag(id='{self.id}', name='{self.name}')"

    def __getattr__(self, name):
        # TODO: Maybe switch to using @property instead
        if name in ["id", "name", "as_dict"]:
            self.as_dict = self.info()
            self.__extract_from_data()
            return self.__getattribute__(name)

        raise AttributeError(f"{name} doesn't exist on PyTok.api.Hashtag")
