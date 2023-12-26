from __future__ import annotations

import json
import re
import time
from urllib.parse import urlparse, urlencode
from attr import has

import requests

from ..exceptions import *
from ..helpers import extract_tag_contents, add_if_not_replace

from typing import TYPE_CHECKING, ClassVar, Iterator, Optional

if TYPE_CHECKING:
    from ..tiktok import PyTok
    from .video import Video

from .base import Base


class User(Base):
    """
    A TikTok User.

    Example Usage
    ```py
    user = api.user(username='therock')
    # or
    user_id = '5831967'
    sec_uid = 'MS4wLjABAAAA-VASjiXTh7wDDyXvjk10VFhMWUAoxr8bgfO1kAL1-9s'
    user = api.user(user_id=user_id, sec_uid=sec_uid)
    ```

    """

    parent: ClassVar[PyTok]

    user_id: str
    """The user ID of the user."""
    sec_uid: str
    """The sec UID of the user."""
    username: str
    """The username of the user."""
    as_dict: dict
    """The raw data associated with this user."""

    def __init__(
        self,
        username: Optional[str] = None,
        user_id: Optional[str] = None,
        sec_uid: Optional[str] = None,
        data: Optional[dict] = None,
    ):
        """
        You must provide the username or (user_id and sec_uid) otherwise this
        will not function correctly.
        """
        self.__update_id_sec_uid_username(user_id, sec_uid, username)
        if data is not None:
            self.as_dict = data
            self.__extract_from_data()

    def info(self, **kwargs):
        """
        Returns a dictionary of TikTok's User object

        Example Usage
        ```py
        user_data = api.user(username='therock').info()
        ```
        """
        return self.info_full(**kwargs)

    async def info_full(self, **kwargs) -> dict:
        """
        Returns a dictionary of information associated with this User.
        Includes statistics about this user.

        Example Usage
        ```py
        user_data = api.user(username='therock').info_full()
        ```
        """

        # TODO: Find the one using only user_id & sec_uid
        if not self.username:
            raise TypeError(
                "You must provide the username when creating this class to use this method."
            )

        page = self.parent._page

        url = f"https://www.tiktok.com/@{self.username}"
        if page.url != url:
            async with page.expect_request(url) as event:
                await page.goto(url)
                request = await event.value
                response = await request.response()
                if response.status >= 300:
                    raise NotAvailableException("Content is not available")

        await self.wait_for_content_or_captcha('css=[data-e2e=user-post-item]')

        data_responses = self.get_responses('api/user/detail')
        
        if len(data_responses) > 0:
            data_response = data_responses[-1]
            data = await data_response.json()
            user = data["userInfo"]
        else:
            # get initial html data
            html_body = await page.content()
            tag_contents = extract_tag_contents(html_body)
            data = json.loads(tag_contents)

            user = data["UserModule"]["users"][self.username] | data["UserModule"]["stats"][self.username]

        self.as_dict = user
        return user

    async def videos(self, count=None, batch_size=100, **kwargs) -> Iterator[Video]:
        """
        Returns an iterator yielding Video objects.

        - Parameters:
            - count (int): The amount of videos you want returned.
            - cursor (int): The unix epoch to get uploaded videos since.

        Example Usage
        ```py
        user = api.user(username='therock')
        for video in user.videos(count=100):
            # do something
        ```
        """
        try:
            async for video in self._get_videos_api(count, batch_size, **kwargs):
                yield video
        except ApiFailedException:
            async for video in self._get_videos_scraping(count):
                yield video


    async def _get_videos_api(self, count, batch_size, **kwargs) -> Iterator[Video]:
        amount_yielded = 0
        cursor = 0
        final_cursor = 9999999999999999999999999999999

        all_scraping = True
        if all_scraping or 'videos' not in self.parent.request_cache:
            all_videos, finished, final_cursor = await self._get_api_videos_and_req(count)

            amount_yielded += len(all_videos)
            for video in all_videos:
                yield self.parent.video(data=video)

            if finished:
                return

        data_request = self.parent.request_cache['videos']

        video_ids = set(v['id'] for v in all_videos)

        try:
            count = min(count, self.as_dict['stats']['videoCount'])


            next_url = add_if_not_replace(data_request.url, "count=([0-9]+)", f"count={count}", f"&count={count}")
            r = requests.get(next_url, headers=data_request.headers)

            if r.status_code != 200:
                raise ApiFailingException(f"Failed to get videos from API with status code {r.status_code}")

            res = r.json()
            videos = res.get('itemList', [])
            for video in videos:
                if video['id'] not in video_ids:
                    yield self.parent.video(data=video)

            return
        except Exception:
            print("Failed to get videos all at once, trying in batches...")
            pass

        if count is None:
            count = 0

        while amount_yielded < count and cursor < final_cursor:
            
            next_url = add_if_not_replace(data_request.url, "id=([0-9]+)", f"id={self.user_id}", f"&id={self.user_id}")
            next_url = add_if_not_replace(next_url, "secUid=([0-9]+)", f"secUid={self.sec_uid}", f"&secUid={self.sec_uid}")
            next_url = add_if_not_replace(next_url, "cursor=([0-9]+)", f"cursor={cursor}", f"&cursor={cursor}")

            r = requests.get(next_url, headers=data_request.headers)
            res = r.json()

            if res.get('type') == 'verify':
                # force new request for cache
                self._get_api_videos_and_req(count - amount_yielded)

            videos = res.get('itemList', [])
            cursor = int(res['cursor'])

            if videos:
                amount_yielded += len(videos)
                for video in videos:
                    yield self.parent.video(data=video)

            has_more = res.get("hasMore")
            if not has_more:
                self.parent.logger.info(
                    "TikTok isn't sending more TikToks beyond this point."
                )
                return

            self.parent.request_delay()

    async def _get_api_videos_and_req(self, count):
        all_videos = []

        video_responses = self.get_responses('api/post/item_list')
        for video_response in video_responses:
            try:
                video_data = await video_response.json()
                if video_data.get('itemList'):
                    videos = video_data['itemList']
                    all_videos += videos
                    finished = video_data.get('hasMore') is False
                    final_cursor = int(video_data['cursor'])
                    break
            except Exception:
                pass

        self.parent.request_cache['videos'] = video_responses[-1]

        return all_videos, finished, final_cursor

    async def _get_videos_scraping(self, count):
        page = self.parent._page

        url = f"https://www.tiktok.com/@{self.username}"
        if page.url != url:
            await page.goto(url)
            self.check_initial_call(url)
        await self.wait_for_content_or_captcha('user-post-item')

        video_pull_method = 'scroll'
        if video_pull_method == 'scroll':
            for video in self._get_videos_scroll(count):
                yield video
        elif video_pull_method == 'individual':
            for video in self._get_videos_individual(count):
                yield video

    async def _get_videos_individual(self, count):
        page = self.parent._page

        await page.locator("[data-e2e=user-post-item]").click()

        self.wait_for_content_or_captcha('browse-video')

        still_more = True
        all_videos = []

        while still_more:
            html_req_path = page.url
            initial_html_request = self.get_requests(html_req_path)[0]
            html_body = self.get_response_body(initial_html_request)
            tag_contents = extract_tag_contents(html_body)
            res = json.loads(tag_contents)

            all_videos += res['itemList']

            if still_more:
                await page.locator("[data-e2e=browse-video]").press('ArrowDown')

    def _load_each_video(self, videos):
        page = self.parent._page

        # get description elements with identifiable links
        all_desc_elements = page.locator("[data-e2e=user-post-item-desc]").elements

        video_elements = []
        for video in videos:
            for desc_element in all_desc_elements:
                if video['id'] in desc_element.children()[0].get_attribute('href'):
                    # get sibling element of video element
                    video_element = desc_element.locator('//..').children()[0]
                    video_elements.append((video, video_element))
                    break
            else:
                pass
                # TODO log this
                # raise Exception(f"Could not find video element for video {video['id']}")

        for i, (video, element) in enumerate(video_elements):
            self.scroll_to(element.location['y'])
            element.hover()
            try:
                play_path = urlparse(video['video']['playAddr']).path
            except KeyError:
                print(f"Missing JSON attributes for video: {video['id']}")
                continue

            try:
                self.wait_for_requests(play_path)
            except Exception:
                print(f"Failed to load video file for video: {video['id']}")
            self.parent.request_delay()

    def _get_videos_scroll(self, count):

        # get initial html data
        html_req_path = f"@{self.username}"
        initial_html_request = self.get_requests(html_req_path)[0]
        html_body = self.get_response_body(initial_html_request)
        tag_contents = extract_tag_contents(html_body)
        res = json.loads(tag_contents)

        amount_yielded = 0
        all_videos = []

        if 'ItemModule' in res:
            videos = list(res['ItemModule'].values())

            video_users = res["UserModule"]["users"]

            for video in videos:
                video['author'] = video_users[video['author']]

            self._load_each_video(videos)

            amount_yielded += len(videos)
            video_objs = [self.parent.video(data=video) for video in videos]

            for video in video_objs:
                yield video

            has_more = res['ItemList']['user-post']['hasMore']
            if not has_more:
                User.parent.logger.info(
                    "TikTok isn't sending more TikToks beyond this point."
                )
                return
            
            if count and amount_yielded >= count:
                return

        data_request_path = "api/post/item_list"
        data_urls = []
        tries = 1
        MAX_TRIES = 10

        valid_data_request = False
        cursors = []
        while not valid_data_request:
            for _ in range(tries):
                self.parent.request_delay()
                self.slight_scroll_up()
                self.parent.request_delay()
                self.scroll_to_bottom()
            try:
                self.wait_for_requests(data_request_path, timeout=tries*4)
            except TimeoutException:
                tries += 1
                if tries > MAX_TRIES:
                    raise
                continue

            data_requests = [req for req in self.get_requests(data_request_path) if req.url not in data_urls]

            if not data_requests:
                tries += 1
                if tries > MAX_TRIES:
                    raise EmptyResponseException('TikTok backend broke')
                continue

            for data_request in data_requests:
                data_urls.append(data_request.url)
                res_body = self.get_response_body(data_request)

                if not res_body:
                    tries += 1
                    if tries > MAX_TRIES:
                        raise EmptyResponseException('TikTok backend broke')
                    continue

                valid_data_request = True
                self.parent.request_cache['videos'] = data_request

                res = json.loads(res_body)
                videos = res.get("itemList", [])
                cursors.append(int(res['cursor']))

                self._load_each_video(videos)

                amount_yielded += len(videos)
                video_objs = [self.parent.video(data=video) for video in videos]

                for video in video_objs:
                    yield video

                if count and amount_yielded >= count:
                    return

                has_more = res.get("hasMore", False)
                if not has_more:
                    User.parent.logger.info(
                        "TikTok isn't sending more TikToks beyond this point."
                    )
                    return

        return


    def liked(self, count: int = 30, cursor: int = 0, **kwargs) -> Iterator[Video]:
        """
        Returns a dictionary listing TikToks that a given a user has liked.

        **Note**: The user's likes must be **public** (which is not the default option)

        - Parameters:
            - count (int): The amount of videos you want returned.
            - cursor (int): The unix epoch to get uploaded videos since.

        Example Usage
        ```py
        for liked_video in api.user(username='public_likes'):
            # do something
        ```
        """
        processed = User.parent._process_kwargs(kwargs)
        kwargs["custom_device_id"] = processed.device_id

        amount_yielded = 0
        first = True

        if self.user_id is None and self.sec_uid is None:
            self.__find_attributes()

        while amount_yielded < count:
            query = {
                "count": 30,
                "id": self.user_id,
                "type": 2,
                "secUid": self.sec_uid,
                "cursor": cursor,
                "sourceType": 9,
                "appId": 1233,
                "region": processed.region,
                "priority_region": processed.region,
                "language": processed.language,
            }
            path = "api/favorite/item_list/?{}&{}".format(
                User.parent._add_url_params(), urlencode(query)
            )

            res = self.parent.get_data(path, **kwargs)

            if "itemList" not in res.keys():
                if first:
                    User.parent.logger.error("User's likes are most likely private")
                return

            videos = res.get("itemList", [])
            amount_yielded += len(videos)
            for video in videos:
                amount_yielded += 1
                yield self.parent.video(data=video)

            if not res.get("hasMore", False) and not first:
                User.parent.logger.info(
                    "TikTok isn't sending more TikToks beyond this point."
                )
                return

            cursor = res["cursor"]
            first = False

    def __extract_from_data(self):
        data = self.as_dict
        keys = data.keys()

        if "user_info" in keys:
            self.__update_id_sec_uid_username(
                data["user_info"]["uid"],
                data["user_info"]["sec_uid"],
                data["user_info"]["unique_id"],
            )
        elif "uniqueId" in keys:
            self.__update_id_sec_uid_username(
                data["id"], data["secUid"], data["uniqueId"]
            )

        if None in (self.username, self.user_id, self.sec_uid):
            User.parent.logger.error(
                f"Failed to create User with data: {data}\nwhich has keys {data.keys()}"
            )

    def __update_id_sec_uid_username(self, id, sec_uid, username):
        self.user_id = id
        self.sec_uid = sec_uid
        self.username = username

    def __find_attributes(self) -> None:
        # It is more efficient to check search first, since self.user_object() makes HTML request.
        found = False
        for u in self.parent.search.users(self.username):
            if u.username == self.username:
                found = True
                self.__update_id_sec_uid_username(u.user_id, u.sec_uid, u.username)
                break

        if not found:
            user_object = self.info()
            self.__update_id_sec_uid_username(
                user_object["id"], user_object["secUid"], user_object["uniqueId"]
            )

    def __repr__(self):
        return self.__str__()

    def __str__(self):
        return f"PyTok.user(username='{self.username}', user_id='{self.user_id}', sec_uid='{self.sec_uid}')"

    def __getattr__(self, name):
        if name in ["as_dict"]:
            self.as_dict = self.info()
            self.__extract_from_data()
            return self.__getattribute__(name)

        raise AttributeError(f"{name} doesn't exist on PyTok.api.User")
