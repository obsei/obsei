# Code in this file is copied from https://github.com/egbertbouman/youtube-comment-downloader/blob/master/youtube_comment_downloader/downloader.py
# and modified to fit the needs of this project. When code from youtube-comment-downloader was copied it was MIT licensed.
# Code Commit: https://github.com/egbertbouman/youtube-comment-downloader/commit/9a15b8e3fbaebad660875409fb1bbe74db17f304

import json
import logging
import time
import re
from datetime import datetime, timezone

import dateparser
from typing import Optional, Any, List, Dict

import requests
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class YouTubeCommentExtractor(BaseModel):
    _YT_URL: str = 'https://www.youtube.com'
    _YT_CFG_REGEX: str = r'ytcfg\.set\s*\(\s*({.+?})\s*\)\s*;'
    _YT_INITIAL_DATA_REGEX: str = r'(?:window\s*\[\s*["\']ytInitialData["\']\s*\]|ytInitialData)\s*=\s*({.+?})\s*;\s*(?:var\s+meta|</script|\n)'
    video_url: str
    user_agent: str = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/79.0.3945.130 Safari/537.36'
    sort_by: int = 1  # 0 = sort by popular, 1 = sort by recent
    max_comments: Optional[int] = 20
    fetch_replies: bool = False
    lang_code: Optional[str] = None
    sleep_time: float = 0.1
    request_retries: int = 5

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        if self.sort_by not in [0, 1]:
            raise ValueError('sort_by must be either 0 or 1')

    @staticmethod
    def _regex_search(text, pattern: str, group: int = 1) -> str:
        match = re.search(pattern, text)
        return match.group(group) if match else ''

    def _ajax_request(self, session, endpoint, ytcfg):
        url = self._YT_URL + endpoint['commandMetadata']['webCommandMetadata']['apiUrl']

        data = {'context': ytcfg['INNERTUBE_CONTEXT'],
                'continuation': endpoint['continuationCommand']['token']}

        for _ in range(self.request_retries):
            response = session.post(url, params={'key': ytcfg['INNERTUBE_API_KEY']}, json=data)
            if response.status_code == 200:
                return response.json()
            if response.status_code in [403, 413]:
                return {}
            else:
                time.sleep(self.sleep_time)

    @staticmethod
    def _search_dict(partial: Any, search_key: str):
        stack = [partial]
        while stack:
            current_item = stack.pop()
            if isinstance(current_item, dict):
                for key, value in current_item.items():
                    if key == search_key:
                        yield value
                    else:
                        stack.append(value)
            elif isinstance(current_item, list):
                for value in current_item:
                    stack.append(value)

    def _fetch_comments(self, until_datetime: Optional[datetime] = None):
        session = requests.Session()
        session.headers['User-Agent'] = self.user_agent
        response = session.get(self.video_url)

        if response.request and response.request.url and 'uxe=' in response.request.url:
            session.cookies.set('CONSENT', 'YES+cb', domain='.youtube.com')
            response = session.get(self.video_url)

        html = response.text
        ytcfg = json.loads(self._regex_search(html, self._YT_CFG_REGEX))
        if not ytcfg:
            return  # Unable to extract configuration
        if self.lang_code:
            ytcfg['INNERTUBE_CONTEXT']['client']['hl'] = self.lang_code

        data = json.loads(self._regex_search(html, self._YT_INITIAL_DATA_REGEX))

        section = next(self._search_dict(data, 'itemSectionRenderer'), None)
        renderer = next(self._search_dict(section, 'continuationItemRenderer'), None) if section else None
        if not renderer:
            # Comments disabled?
            return

        needs_sorting = self.sort_by != 0
        continuations = [renderer['continuationEndpoint']]
        while continuations:
            continuation = continuations.pop()
            response = self._ajax_request(session, continuation, ytcfg)

            if not response:
                break
            if list(self._search_dict(response, 'externalErrorMessage')):
                logger.warning('Error returned from server: %s', next(self._search_dict(response, 'externalErrorMessage')))
                return

            if needs_sorting:
                sub_menu: Dict[str, Any] = next(self._search_dict(response, 'sortFilterSubMenuRenderer'), {})
                sort_menu = sub_menu.get('subMenuItems', [])
                if self.sort_by < len(sort_menu):
                    continuations = [sort_menu[self.sort_by]['serviceEndpoint']]
                    needs_sorting = False
                    continue
                raise RuntimeError('Failed to set sorting')

            actions = list(self._search_dict(response, 'reloadContinuationItemsCommand')) + \
                      list(self._search_dict(response, 'appendContinuationItemsAction'))

            for action in actions:
                for item in action.get('continuationItems', []):
                    if action['targetId'] == 'comments-section':
                        # Process continuations for comments and replies.
                        continuations[:0] = [ep for ep in self._search_dict(item, 'continuationEndpoint')]
                    if self.fetch_replies:
                        if action['targetId'].startswith('comment-replies-item') and 'continuationItemRenderer' in item:
                            # Process the 'Show more replies' button
                            continuations.append(next(self._search_dict(item, 'buttonRenderer'))['command'])

            for comment in reversed(list(self._search_dict(response, 'commentRenderer'))):
                if not self.fetch_replies and "." in comment['commentId']:
                    continue

                comment_time = dateparser.parse(
                    comment['publishedTimeText']['runs'][0]['text']
                )

                if comment_time:
                    comment_time = comment_time.replace(tzinfo=timezone.utc)
                    if until_datetime and until_datetime > comment_time:
                        return

                yield {'comment_id': comment['commentId'],
                       'text': ''.join([c['text'] for c in comment['contentText'].get('runs', [])]),
                       'time': comment_time,
                       'author': comment.get('authorText', {}).get('simpleText', ''),
                       'channel': comment['authorEndpoint']['browseEndpoint'].get('browseId', ''),
                       'votes': comment.get('voteCount', {}).get('simpleText', '0'),
                       'photo': comment['authorThumbnail']['thumbnails'][-1]['url'],
                       'heart': next(self._search_dict(comment, 'isHearted'), False)}

            time.sleep(self.sleep_time)

    def fetch_comments(self, until_datetime: Optional[datetime] = None) -> List[Dict[str, Any]]:
        comments: List[Dict[str, Any]] = []
        for comment in self._fetch_comments(until_datetime=until_datetime):
            comments.append(comment)
            if self.max_comments and self.max_comments == len(comments):
                break

        return comments
