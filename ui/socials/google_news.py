from database import *
from ui.views.utils import save_generate_config, execute_listening
import datetime

ct = datetime.datetime.now()


def save_google_news_analyze(generate_config, progress_show):
    filtered_app_url = [value for value in generate_config['source_config']['query'] if value != '']

    if progress_show and len(filtered_app_url) == 0:
        progress_show.code(f"❗❗❗ Processing Failed!! 😞😞😞 \n 👉 (`query` in config should not "
                           f"be empty or None)")
        progress_show = None
        return [progress_show]

    try:
        with client.start_session() as session:
            # Start a transaction
            with session.start_transaction():
                config = save_generate_config(generate_config)
                save_keywords(config)
                data_informer = execute_listening(generate_config, progress_show)
                session.abort_transaction()
                return [progress_show, data_informer]
    except pymongo.errors.PyMongoError as e:
        print("Error:", str(e))

    except Exception as ex:
        if progress_show:
            progress_show.code(f"❗❗❗ Processing Failed!! 😞😞😞 \n 👉 ({str(ex)})")

        raise ex


def save_keywords(generate_config):
    array_keyword = []
    for keyword in generate_config['source_config']['query']:
        array_url_keyword = {'generated_config_id': generate_config['_id'], 'keyword': keyword,
                             'url': '',
                             'created_at': ct}
        array_keyword.append(array_url_keyword)
    if len(array_keyword) > 0:
        database.urls.insert_many(array_keyword)
