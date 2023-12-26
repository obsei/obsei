from __future__ import annotations

import logging
from urllib.parse import urlencode

from .video import Video
from .sound import Sound
from .user import User
from .hashtag import Hashtag

from typing import TYPE_CHECKING, Iterator

if TYPE_CHECKING:
    from ..tiktok import PyTok


class Trending:
    """Contains static methods related to trending."""

    parent: PyTok

    @staticmethod
    def videos(count=30, **kwargs) -> Iterator[Video]:
        """
        Returns Videos that are trending on TikTok.

        - Parameters:
            - count (int): The amount of videos you want returned.
        """

        raise NotImplementedError()
