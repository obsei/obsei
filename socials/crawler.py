from database import *
from utils import save_generate_config, execute_listening
import datetime

ct = datetime.datetime.now()


def save_crawler_analyze(generate_config, progress_show):
    filtered_url = [value for value in generate_config['source_config']['urls'] if value != '']

    if progress_show and len(filtered_url) == 0:
        progress_show.code(f"❗❗❗ Processing Failed!! 😞😞😞 \n 👉 (`urls` in config should not "
                           f"be empty or None)")
        progress_show = None
        return [progress_show]

    try:
        with client.start_session() as session:
            # Start a transaction
            with session.start_transaction():
                config = save_generate_config(generate_config)
                save_website_url(config)
                data_informer = execute_listening(generate_config, progress_show)
                session.abort_transaction()
                return [progress_show, data_informer]

    except pymongo.errors.PyMongoError as e:
        print("Error:", str(e))

    except Exception as ex:
        if progress_show:
            progress_show.code(f"❗❗❗ Processing Failed!! 😞😞😞 \n 👉 ({str(ex)})")

        raise ex


def save_website_url(generate_config):
    array_url = []
    for url in generate_config['source_config']['urls']:
        array_url.append({'generated_config_id': generate_config['_id'],
                          'url': url,
                          'created_at': ct}
                         )
    if len(array_url) > 0:
        database.urls.insert_many(array_url)
