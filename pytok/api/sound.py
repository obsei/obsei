from __future__ import annotations
from os import path

import json

from urllib.parse import quote, urlencode

from ..helpers import extract_tag_contents
from ..exceptions import *

from typing import TYPE_CHECKING, ClassVar, Iterator, Optional

if TYPE_CHECKING:
    from ..tiktok import PyTok
    from .user import User
    from .video import Video


class Sound:
    """
    A TikTok Sound/Music/Song.

    Example Usage
    ```py
    song = api.song(id='7016547803243022337')
    ```
    """

    parent: ClassVar[PyTok]

    id: str
    """TikTok's ID for the sound"""
    title: Optional[str]
    """The title of the song."""
    author: Optional[User]
    """The author of the song (if it exists)"""

    def __init__(self, id: Optional[str] = None, data: Optional[str] = None):
        """
        You must provide the id of the sound or it will not work.
        """
        if data is not None:
            self.as_dict = data
            self.__extract_from_data()
        elif id is None:
            raise TypeError("You must provide id parameter.")
        else:
            self.id = id

    def info(self, use_html=False, **kwargs) -> dict:
        """
        Returns a dictionary of TikTok's Sound/Music object.

        - Parameters:
            - use_html (bool): If you want to perform an HTML request or not.
                Defaults to False to use an API call, which shouldn't get detected
                as often as an HTML request.


        Example Usage
        ```py
        sound_data = api.sound(id='7016547803243022337').info()
        ```
        """
        raise NotImplementedError()

    def info_full(self, **kwargs) -> dict:
        """
        Returns all the data associated with a TikTok Sound.

        This makes an API request, there is no HTML request option, as such
        with Sound.info()

        Example Usage
        ```py
        sound_data = api.sound(id='7016547803243022337').info_full()
        ```
        """
        raise NotImplementedError()

    def videos(self, count=30, offset=0, **kwargs) -> Iterator[Video]:
        """
        Returns Video objects of videos created with this sound.

        - Parameters:
            - count (int): The amount of videos you want returned.
            - offset (int): The offset of videos you want returned.

        Example Usage
        ```py
        for video in api.sound(id='7016547803243022337').videos():
            # do something
        ```
        """
        raise NotImplementedError()

    def __extract_from_data(self):
        data = self.as_dict
        keys = data.keys()

        self.id = data.get("id")
        self.title = data.get("title")

        if data.get("authorName") is not None:
            self.author = self.parent.user(username=data["authorName"])

        if self.id is None:
            Sound.parent.logger.error(
                f"Failed to create Sound with data: {data}\nwhich has keys {data.keys()}"
            )

    def __ensure_valid(self):
        if self.id == "":
            raise SoundRemovedException("This sound has been removed!")

    def __repr__(self):
        return self.__str__()

    def __str__(self):
        return f"PyTok.sound(id='{self.id}')"

