from database import *
from utils import save_generate_config, execute_workflow, get_list_urls
import datetime

ct = datetime.datetime.now()


def save_crawler_analyze(generate_config, log_component, progress_show):
    filtered_url = [value for value in generate_config['source_config']['urls'] if value != '']

    if progress_show and len(filtered_url) == 0:
        progress_show.code(f"❗❗❗ Processing Failed!! 😞😞😞 \n 👉 (`urls` in config should not "
                           f"be empty or None)")
        progress_show = None

        return progress_show

    try:
        with client.start_session() as session:
            # Start a transaction
            with session.start_transaction():
                config = save_generate_config(generate_config)
                save_website_url(config)
                execute_crawler(config, log_component)
                session.abort_transaction()
        client.close()

    except pymongo.errors.PyMongoError as e:
        print("Error:", str(e))

    except Exception as ex:
        if progress_show:
            progress_show.code(f"❗❗❗ Processing Failed!! 😞😞😞 \n 👉 ({str(ex)})")

        raise ex

    return progress_show


def execute_crawler(generate_config, log_component):
    urls_table = get_list_urls(generate_config['_id'])
    for record in urls_table:
        generate_config['source_config']['urls'] = [record['url']]
        execute_workflow(generate_config, log_component, record["_id"], generate_config['user_id'])


def save_website_url(generate_config):
    array_url = []
    for url in generate_config['source_config']['urls']:
        array_url.append({'generated_config_id': generate_config['_id'],
                          'url': url,
                          'created_at': ct}
                         )
    if len(array_url) > 0:
        database.urls.insert_many(array_url)
