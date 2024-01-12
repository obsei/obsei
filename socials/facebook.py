from database import *
from utils import save_generate_config, execute_workflow, get_list_urls
import datetime

ct = datetime.datetime.now()

def save_facebook_analyze(generate_config, log_component, progress_show):
    urls = generate_config['source_config']['urls']
    filtered_urls = [value for value in urls if value != '']

    if progress_show and len(filtered_urls) == 0:
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
                execute_facebook_url(config, log_component)
                session.abort_transaction()

    except pymongo.errors.PyMongoError as e:
        print("Error:", str(e))

    except Exception as ex:
        if progress_show:
            progress_show.code(f"❗❗❗ Processing Failed!! 😞😞😞 \n 👉 ({str(ex)})")

        raise ex

    return progress_show


def execute_facebook_url(generate_config, log_component):
    urls_table = get_list_urls(generate_config['_id'])
    for record in urls_table:
        generate_config['source_config']['urls'] = record['url']
        execute_workflow(generate_config, log_component, record["_id"], generate_config['user_id'])

def convert_data_urls(generate_config):
    array_urls = []
    for url in generate_config['source_config']['urls']:
        if url == '':
            continue
        array_urls.append({'generated_config_id': generate_config['_id'], 'url': url, 'created_at': ct})
    if len(array_urls) > 0:
        database.urls.insert_many(array_urls)


