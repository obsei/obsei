from database import *
from utils import save_generate_config, execute_listening
import datetime

ct = datetime.datetime.now()


def save_reddit_rss_analyze(generate_config, progress_show):
    filtered_url = [value for value in generate_config['source_config']['url'] if value != '']
    if progress_show and len(filtered_url) == 0:
        progress_show.code(f"❗❗❗ Processing Failed!! 😞😞😞 \n 👉 (`url` or `keywords` in config should not "
                           f"be empty or None)")
        progress_show = None
        return [progress_show]
    try:
        with client.start_session() as session:
            # Start a transaction
            with session.start_transaction():
                generate_config = save_generate_config(generate_config)
                convert_data_urls(generate_config)
                data_informer = execute_listening(generate_config, progress_show)
                session.abort_transaction()
                return [progress_show, data_informer]
    except pymongo.errors.PyMongoError as e:
        print("Error:", str(e))

    except Exception as ex:
        if progress_show:
            progress_show.code(f"❗❗❗ Processing Failed!! 😞😞😞 \n 👉 ({str(ex)})")

        raise ex


def get_generate_config(config_id):
    results = database.generate_configs.find_one({'_id': ObjectId(config_id)})
    return results


def convert_data_urls(generate_config):
    if 'url' in generate_config['source_config']:
        array_urls = []
        for url in generate_config['source_config']['url']:
            if url == '':
                continue

            array_url = {'generated_config_id': generate_config['_id'], 'url': url, 'created_at': ct}
            array_urls.append(array_url)
        if len(array_urls) > 0:
            database.urls.insert_many(array_urls)
