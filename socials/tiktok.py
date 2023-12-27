from database import *
from utils import save_generate_config, execute_workflow, get_list_urls
import datetime

ct = datetime.datetime.now()


def save_tiktok_analyze(generate_config, log_component, progress_show):
    filtered_video_url = [value for value in generate_config['source_config']['video_url'] if value != '']

    if progress_show and len(filtered_video_url) == 0:
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
                execute_tiktok_url(config, log_component)
                session.abort_transaction()
        client.close()

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
    for url in generate_config['source_config']['video_url']:
        if url == '':
            continue
        array_url = {'generated_config_id': generate_config['_id'], 'url': url, 'created_at': ct}
        array_urls.append(array_url)

    if len(array_urls) > 0:
        save_urls(array_urls)
