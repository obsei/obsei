from database import *

import  logging, pathlib, re, sys, uuid, yaml, inspect, textwrap, time

import streamlit as st

from obsei.configuration import ObseiConfiguration
from rq import Queue
from redis import Redis
from queues.social_listening import execute_workflow

logger = logging.getLogger(__name__)
logging.basicConfig(stream=sys.stdout, level=logging.INFO)


def save_generate_config(config_generated):
    generate_configs_table = database.generate_configs
    generate_configs_table.insert_one(config_generated)

    print("Config inserted successfully")

    return config_generated


def get_obsei_config(current_path, file_name):
    return ObseiConfiguration(
        config_path=current_path,
        config_filename=file_name,
    ).configuration


# @st.cache_data
def get_icon_name(name, icon='', icon_size=40, font_size=1):
    if not name:
        return f'<img style="vertical-align:middle;margin:5px 5px" src="{icon}" width="{icon_size}" height="{icon_size}">'
    return (
        f'<p style="font-size:{font_size}px">'
        # f'<img style="vertical-align:middle;margin:1px 5px" src="{icon}" width="{icon_size}" height="{icon_size}">'
        f"{name}</p>"
    )


def render_config(config, component, help_str=None, parent_key=None):
    if config is None:
        return

    prefix = "" if parent_key is None else f"{parent_key}."
    if help_str is not None:
        with component.expander("Info", False):
            help_area = "\n".join(help_str)
            st.code(f"{help_area}")
    for k, v in config.items():
        if k == "_target_":
            continue

        if isinstance(v, dict):
            render_config(v, component, None, k)
        elif isinstance(v, list):
            if len(v) == 0:
                continue
            is_object = isinstance(v[0], dict)
            if is_object:
                for idx, sub_element in enumerate(v):
                    render_config(sub_element, component, None, f"{k}[{idx}]")
            else:
                text_data = component.text_area(
                    f"{prefix}{k}", ", ".join(v), help="Comma separated list"
                )
                text_list = text_data.split(",")
                config[k] = [text.strip() for text in text_list]
        elif isinstance(v, bool):
            options = [True, False]
            selected_option = component.radio(f"{prefix}{k}", options, options.index(v))
            config[k] = bool(selected_option)
        else:
            tokens = k.split("_")
            is_secret = tokens[-1] in ["key", "password", "token", "secret"]
            hint = (
                "Enter value"
                if "lookup" not in tokens
                else "Format: `<number><d|h|m>` d=day, h=hour & m=minute"
            )
            config[k] = component.text_input(
                f"{prefix}{k}",
                v,
                type="password" if is_secret else "default",
                help=hint,
            )


def execute_listening(generate_config, progress_show):
    urls_table = database.urls.find({'generated_config_id': ObjectId(generate_config['_id'])})
    records = []
    for record in urls_table:
        records.append(record)

    redis_conn = Redis()
    queue = Queue(connection=redis_conn)

    data = queue.enqueue(execute_workflow, args=(records, generate_config))

    while data.result is None:
        progress_show.code("🏄🏄🏄 Processing 🐢")
        time.sleep(1)
        progress_show.code("🏄🏄🏄 Processing 🐢🐢")
        time.sleep(1)
        progress_show.code("🏄🏄🏄 Processing 🐢🐢🐢")
        time.sleep(1)

    return data.result


def show_data_table(generate_config, log_components=None, analyzer_response_list=None, progress_show=None):
    try:
        obsei_configuration = ObseiConfiguration(configuration=generate_config)

        sink_config = obsei_configuration.initialize_instance("sink_config")
        sink = obsei_configuration.initialize_instance("sink")

        log_components["analyzer"].write([vars(response) for response in analyzer_response_list])

        sink_response_list = sink.send_data(analyzer_response_list, sink_config)

        if sink.TYPE == 'Pandas':
            log_components["sink"].write(sink_response_list)
        elif sink_response_list is not None:
            log_components["sink"].write([vars(response) for response in sink_response_list])
        else:
            log_components["sink"].write("No Data")

    except Exception as ex:
        if progress_show:
            progress_show.code(f"❗❗❗ Processing Failed!! 😞😞😞 \n 👉 ({str(ex)})")

        raise ex


def check_system(generate_config, params, progress_show):
    if 'uid' in params:
        generate_config['user_id'] = params['uid'][0]
    else:
        progress_show.code(f"❗❗❗ Processing Failed!! 😞😞😞 \n 👉 (Please login Vplaner)")
        progress_show = None
        print("No 'uid' parameter found in the URL.")

    return progress_show

