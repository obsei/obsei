from database import *
from utils import save_generate_config, execute_workflow, get_list_urls

import subprocess, datetime, time

ct = datetime.datetime.now()


def save_tiktok_analyze(generate_config, log_component, progress_show):
    token = generate_config['source_config']['ms_token']
    keywords = generate_config['source_config']['keywords']
    video_url = generate_config['source_config']['video_url']
    max_videos = generate_config['source_config']['max_videos']

    filtered_video_url = [value for value in video_url if value != '']
    filtered_keywords = [value for value in keywords if value != '']

    if progress_show and len(filtered_video_url) == 0 and len(filtered_keywords) == 0:
        progress_show.code(f"❗❗❗ Processing Failed!! 😞😞😞 \n 👉 (`video_url` in config should not "
                           f"be empty or None)")
        progress_show = None

        return progress_show

    try:
        with client.start_session() as session:
            # Start a transaction
            with session.start_transaction():
                config = save_generate_config(generate_config)
                convert_data_urls(config)

                if len(filtered_keywords) > 0 :
                    while True:
                        save_url_video_by_keywords(filtered_keywords, max_videos, token, str(config['_id']))
                        time.sleep(2)
                        records = list(database.urls.find({'generated_config_id': ObjectId(config['_id'])}))
                        count_urls = len(records)
                        if count_urls > 0:
                            break
  
                execute_tiktok_url(config, log_component)
                session.abort_transaction()

    except pymongo.errors.PyMongoError as e:
        print("Error:", str(e))

    except Exception as ex:
        if progress_show:
            progress_show.code(f"❗❗❗ Processing Failed!! 😞😞😞 \n 👉 ({str(ex)})")

        raise ex

    return progress_show


def execute_tiktok_url(generate_config, log_component):      
    urls_table = get_list_urls(generate_config['_id'])
    for record in urls_table:
        generate_config['source_config']['video_url'] = record['url']
        execute_workflow(generate_config, log_component, record["_id"], generate_config['user_id'])


def save_urls(object_urls):
    if object_urls is not None:
        database.urls.insert_many(object_urls)


def convert_data_urls(generate_config):
    array_urls = []
    for video_url in generate_config['source_config']['video_url']:
        if video_url == '':
            continue
        array_url = {'generated_config_id': generate_config['_id'], 'url': video_url, 'created_at': ct}
        array_urls.append(array_url)
    if len(array_urls) > 0:
        save_urls(array_urls)


def save_url_video_by_keywords(keywords, max_videos, ms_token, generate_config_id):
    for keyword in keywords:
        keyword = "_".join(keyword.split())
        command = "xvfb-run -a python3 libs/tiktok/search_tiktok.py " + keyword + ' ' + ms_token + ' ' + max_videos + ' ' + generate_config_id
        subprocess.run(command, shell=True, capture_output=True, text=True)