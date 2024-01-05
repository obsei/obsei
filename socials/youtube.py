from database import *
from utils import save_generate_config, execute_workflow, get_list_urls
from youtube_search import YoutubeSearch
import json, datetime, re

ct = datetime.datetime.now()
url_youtube = 'https://www.youtube.com/watch?v='


def execute_youtube(config_id, log_component):
    # đánh index cho các cột cần search
    # vidu:db.data_analyzed.createIndex({ processed_text: "text"})
    # lưu thêm user_id vào các bảng theo user_id trên url
    generate_config = get_generate_config(config_id)

    urls_table = get_list_urls(config_id)
    for record in urls_table:
        generate_config['source_config']['video_url'] = record['url']
        execute_workflow(generate_config, log_component, record["_id"], generate_config['user_id'])


def save_youtube_analyze(generate_config, log_component, progress_show):
    filtered_keywords = [value for value in generate_config['source_config']['keywords'] if value != '']
    filtered_video_url = [value for value in generate_config['source_config']['video_url'] if value != '']

    if progress_show and len(filtered_keywords) == 0 and len(filtered_video_url) == 0:
        progress_show.code(f"❗❗❗ Processing Failed!! 😞😞😞 \n 👉 (`video_url` or `keywords` in config should not "
                           f"be empty or None)")
        progress_show = None

        return progress_show

    try:
        with client.start_session() as session:
            # Start a transaction
            with session.start_transaction():
                generate_config = save_generate_config(generate_config)
                generate_config_converted = get_url_video_by_keywords(generate_config)
                convert_data_urls(generate_config_converted['_id'], generate_config_converted['source_config'])
                execute_youtube(generate_config_converted['_id'], log_component)
                session.abort_transaction()

    except pymongo.errors.PyMongoError as e:
        print("Error:", str(e))

    except Exception as ex:
        if progress_show:
            progress_show.code(f"❗❗❗ Processing Failed!! 😞😞😞 \n 👉 ({str(ex)})")

        raise ex

    return progress_show


def get_generate_config(config_id):
    results = database.generate_configs.find_one({'_id': ObjectId(config_id)})
    return results


def save_urls(object_urls):
    if object_urls is not None:
        database.urls.insert_many(object_urls)


def convert_data_urls(generated_config_id, source_config):
    if 'video_url' in source_config:
        array_urls = []
        for url in source_config['video_url']:
            if url == '':
                continue

            array_url = {'generated_config_id': generated_config_id, 'url': url, 'created_at': ct}
            array_urls.append(array_url)
        if len(array_urls) > 0:
            save_urls(array_urls)

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
                save_urls(array_url)


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
