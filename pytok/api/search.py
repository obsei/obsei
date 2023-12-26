from __future__ import annotations

import json
import time
from typing import TYPE_CHECKING, Iterator, Type
from urllib.parse import urlencode
import re

from .user import User
from .hashtag import Hashtag
from .video import Video
from .base import Base
from ..exceptions import *

if TYPE_CHECKING:
    from ..tiktok import PyTok

import requests
from playwright.async_api import TimeoutError

class Search(Base):
    """Contains static methods about searching."""

    parent: PyTok

    def __init__(self, search_term):
        self.search_term = search_term

    def videos(self, count=28, offset=0, **kwargs) -> Iterator[Video]:
        """
        Searches for Videos

        - Parameters:
            - search_term (str): The phrase you want to search for.
            - count (int): The amount of videos you want returned.
            - offset (int): The offset of videos from your data you want returned.

        Example Usage
        ```py
        for video in api.search.videos('therock'):
            # do something
        ```
        """
        return self.search_type(
            "item", count=count, offset=offset, **kwargs
        )

    def users(self, count=28, offset=0, **kwargs) -> Iterator[User]:
        """
        Searches for users using an alternate endpoint than Search.users

        - Parameters:
            - search_term (str): The phrase you want to search for.
            - count (int): The amount of videos you want returned.

        Example Usage
        ```py
        for user in api.search.users_alternate('therock'):
            # do something
        ```
        """
        return self.search_type(
            "user", count=count, offset=offset, **kwargs
        )

    async def search_type(self, obj_type, count=28, offset=0, **kwargs) -> Iterator:
        """
        Searches for users using an alternate endpoint than Search.users

        - Parameters:
            - search_term (str): The phrase you want to search for.
            - count (int): The amount of videos you want returned.
            - obj_type (str): user | item

        Just use .video & .users
        ```
        """

        if obj_type == "user":
            subdomain = "www"
            subpath = "user"
        elif obj_type == "item":
            subdomain = "us"
            subpath = "video"
        else:
            raise TypeError("invalid obj_type")

        page = self.parent._page

        url = f"https://{subdomain}.tiktok.com/search/{subpath}?q={self.search_term}"
        await page.goto(url)

        self.wait_for_content_or_captcha('search_video-item')

        processed_urls = []
        amount_yielded = 0
        pull_method = 'browser'
        
        path = f"api/search/{obj_type}"

        while amount_yielded < count:
            self.parent.request_delay()

            if pull_method == 'browser':
                search_requests = self.get_requests(path)
                search_requests = [request for request in search_requests if request.url not in processed_urls]
                for request in search_requests:
                    processed_urls.append(request.url)
                    body = self.get_response_body(request)
                    res = json.loads(body)
                    if res.get('type') == 'verify':
                        # this is the captcha denied response
                        continue

                    # When I move to 3.10+ support make this a match switch.
                    if obj_type == "user":
                        for result in res.get("user_list", []):
                            yield User(data=result)
                            amount_yielded += 1

                    if obj_type == "item":
                        for result in res.get("item_list", []):
                            yield Video(data=result)
                            amount_yielded += 1

                    if res.get("has_more", 0) == 0:
                        Search.parent.logger.info(
                            "TikTok is not sending videos beyond this point."
                        )
                        return

                try:
                    load_more_button = self.wait_for_content_or_captcha('search-load-more')
                except TimeoutError:
                    return

                load_more_button.click()

                self.wait_until_not_skeleton_or_captcha('video-skeleton-container')

            
            elif pull_method == 'requests':
                cursor = res["cursor"]
                next_url = re.sub("offset=([0-9]+)", f"offset={cursor}", request.url)

                r = requests.get(next_url, headers=request.headers)
                res = r.json()

                if res.get('type') == 'verify':
                    pull_method = 'browser'
                    continue

                if obj_type == "user":
                    for result in res.get("user_list", []):
                        yield User(data=result)
                        amount_yielded += 1

                if obj_type == "item":
                    for result in res.get("item_list", []):
                        yield Video(data=result)
                        amount_yielded += 1

                if res.get("has_more", 0) == 0:
                    self.parent.logger.info(
                        "TikTok is not sending videos beyond this point."
                    )
                    return
