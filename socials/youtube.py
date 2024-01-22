from database import *
from utils import save_generate_config, execute_listening
from youtube_search import YoutubeSearch
import json, datetime, re

ct = datetime.datetime.now()
url_youtube = 'https://www.youtube.com/watch?v='


def save_youtube_analyze(generate_config, progress_show):
    filtered_keywords = [value for value in generate_config['source_config']['keywords'] if value != '']
    filtered_video_url = [value for value in generate_config['source_config']['video_url'] if value != '']

    if progress_show and len(filtered_keywords) == 0 and len(filtered_video_url) == 0:
        progress_show.code(f"❗❗❗ Processing Failed!! 😞😞😞 \n 👉 (`video_url` or `keywords` in config should not "
                           f"be empty or None)")
        progress_show = None
        return [progress_show]

    try:
        with client.start_session() as session:
            # Start a transaction
            with session.start_transaction():
                generate_config = save_generate_config(generate_config)
                generate_config_converted = get_url_video_by_keywords(generate_config)
                convert_data_urls(generate_config_converted['_id'], generate_config_converted['source_config'])
                data_informer = execute_listening(generate_config, progress_show)
                session.abort_transaction()
                return [progress_show, data_informer]

    except pymongo.errors.PyMongoError as e:
        print("Error:", str(e))

    except Exception as ex:
        if progress_show:
            progress_show.code(f"❗❗❗ Processing Failed!! 😞😞😞 \n 👉 ({str(ex)})")

        raise ex


def convert_data_urls(generated_config_id, source_config):
    if 'video_url' in source_config:
        array_urls = []
        for url in source_config['video_url']:
            if url == '':
                continue

            array_url = {'generated_config_id': generated_config_id, 'url': url, 'created_at': ct}
            array_urls.append(array_url)
        if len(array_urls) > 0:
            database.urls.insert_many(array_urls)

    if 'keywords' in source_config:
        keywords = source_config['keywords']
        for keyword in keywords:
            array_url = []
            for url in keywords[keyword]:
                array_url_keyword = {'generated_config_id': generated_config_id, 'keyword': keyword,
                                     'url': url,
                                     'created_at': ct}
                array_url.append(array_url_keyword)
            if len(array_url) > 0:
                database.urls.insert_many(array_url)


def get_url_video_by_keywords(generate_config):
    if 'keywords' not in generate_config['source_config'] or len(generate_config['source_config']['keywords']) == 0:
        return

    keyword_objects = {}
    for keyword in generate_config['source_config']['keywords']:
        if keyword == '':
            continue

        results = YoutubeSearch(keyword,
                                max_results=int(generate_config['source_config']['max_search_video'])).to_json()
        results_dict = json.loads(results)
        list_url = []
        for video in results_dict['videos']:
            list_url.append(url_youtube + video['id'])

        keyword_objects[keyword] = list_url

    generate_config['source_config']['keywords'] = keyword_objects

    return generate_config
