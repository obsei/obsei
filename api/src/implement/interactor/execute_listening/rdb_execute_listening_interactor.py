from typing import List, Dict, Any
from youtube_search import YoutubeSearch
import json, datetime, time, subprocess
from rq import Queue
from redis import Redis
from queues.social_listening import execute_workflow
from bson import ObjectId
from api.src.interfaces.data.const import (
    DEFAULT_URL_YOUTUBE,
)
from api.src.interfaces.usecase.execute_listening_usecase import (
    GetUrlByKeywordsUseCase,
    SaveUrlByKeywordsUseCase,
    ExecuteListeningUseCase
)
from api.src.interfaces.usecase.listening_config_data import (
    GetListeningConfigOutData
)
from api.src.domain.exceptions import (
    MsTokenTiktokExpired,
)


class RDBGetUrlByKeywordsInteractor(GetUrlByKeywordsUseCase):
    def handle(self, config: GetListeningConfigOutData, db) -> GetListeningConfigOutData:
        target = config.source['target__']
        source_config = self._process_keywords(db, config_id=config.id, source_config=config.source_config,
                                               target=target)
        config.source_config = source_config

        return config

    def _process_keywords(self, db, **kwargs):
        source_config = kwargs.get('source_config')
        target = kwargs.get('target')
        config_id = kwargs.get('config_id')

        if 'keywords' not in source_config or not source_config['keywords']:
            return source_config

        keyword_objects = {}
        if target == 'core.source.youtube_scrapper.YoutubeScrapperSource':
            for keyword in source_config['keywords']:
                if keyword:
                    keyword_objects[keyword] = self._get_urls_youtube(keyword,
                                                                      int(source_config.get('max_search_video', 10)))

        if target == 'core.source.tiktok_scrapper.TiktokScrapperSource':
            timeout = 60
            start_time = time.time()
            while True:
                if time.time() - start_time > timeout:
                    raise MsTokenTiktokExpired

                self._get_urls_tiktok(str(config_id), source_config)
                time.sleep(2)
                urls = list(db.urls.find({'generated_config_id': ObjectId(config_id)}, {"url": 1, '_id': 0}))
                count_urls = len(urls)
                keyword_objects = [entry['url'] for entry in urls]

                if count_urls > 0:
                    break

        source_config['keywords'] = keyword_objects
        return source_config

    def _get_urls_youtube(self, keyword, max_search_video):
        results = YoutubeSearch(keyword, max_results=max_search_video).to_json()
        results_dict = json.loads(results)
        return [DEFAULT_URL_YOUTUBE + video['id'] for video in results_dict.get('videos', [])]

    def _get_urls_tiktok(self, config_id, source_config):
        ms_token = source_config['ms_token']
        max_videos = source_config['max_videos']

        for keyword in source_config['keywords']:
            keyword = "_".join(keyword.split())
            command = "xvfb-run -a python3 libs/tiktok/search_tiktok.py " + keyword + ' ' + ms_token + ' ' + max_videos + ' ' + config_id
            subprocess.run(command, shell=True, capture_output=True, text=True)
        return []


class RDBSaveUrlVideoByKeywordsInteractor(SaveUrlByKeywordsUseCase):
    def handle(self, config_id: str, source_config: List, db) -> list[dict[str, Any] | dict[str, Any]] | list[Any]:
        urls = []
        if source_config['target__'] == 'core.source.youtube_scrapper.YoutubeScrapperConfig':
            urls = self._store_url_from_keyword_youtube_search(config_id, source_config, db)
        if source_config['target__'] == 'core.source.tiktok_scrapper.TiktokScrapperSource':
            urls = source_config['keywords']

        return urls

    def _store_url_from_keyword_youtube_search(self, generated_config_id, source_config, database):
        ct = datetime.datetime.now()
        inserted_records = []

        if 'video_url' in source_config:
            video_urls = [url for url in source_config.get('video_url', []) if url]
            urls_to_insert = [{'generated_config_id': generated_config_id, 'url': url, 'created_at': ct} for url in
                              video_urls]
            if urls_to_insert:
                for url_data in urls_to_insert:
                    filter_criteria = {'url': url_data['url']}
                    update_data = {'$set': url_data}
                    result = database.urls.update_one(filter_criteria, update_data, upsert=True)
                    inserted_records.append({'_id': result.upserted_id, **url_data})

        if 'keywords' in source_config:
            keywords = source_config['keywords']
            for keyword, urls in keywords.items():
                for url in urls:
                    if url:
                        url_data = {'generated_config_id': generated_config_id, 'keyword': keyword, 'url': url,
                                    'created_at': ct}
                        filter_criteria = {'url': url}
                        update_data = {'$set': url_data}
                        result = database.urls.update_one(filter_criteria, update_data, upsert=True)
                        inserted_records.append({'_id': result.upserted_id, **url_data})

        return inserted_records


class RDBExecuteListeningInteractor(ExecuteListeningUseCase):
    def handle(self, config_id: str) -> None:
        redis_conn = Redis()
        queue = Queue(connection=redis_conn)

        queue.enqueue(execute_workflow, args=(config_id, True))
