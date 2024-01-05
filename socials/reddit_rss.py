from database import *
from utils import save_generate_config, execute_workflow, get_list_urls
import datetime

ct = datetime.datetime.now()


def execute_reddit_rss(config_id, log_component):
    generate_config = get_generate_config(config_id)
    urls_table = get_list_urls(config_id)

    for record in urls_table:
        generate_config['source_config']['url'] = record['url']
        execute_workflow(generate_config, log_component, record["_id"], generate_config['user_id'])


def save_reddit_rss_analyze(generate_config, log_component, progress_show):
    filtered_url = [value for value in generate_config['source_config']['url'] if value != '']

    if progress_show and len(filtered_url) == 0:
        progress_show.code(f"❗❗❗ Processing Failed!! 😞😞😞 \n 👉 (`url` or `keywords` in config should not "
                           f"be empty or None)")
        progress_show = None

        return progress_show

    try:
        with client.start_session() as session:
            # Start a transaction
            with session.start_transaction():
                generate_config = save_generate_config(generate_config)
                convert_data_urls(generate_config)
                execute_reddit_rss(generate_config['_id'], log_component)
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
