from database import *

import base64, logging, pathlib, re, sys, uuid, yaml, inspect, textwrap

import streamlit as st

from obsei.configuration import ObseiConfiguration

logger = logging.getLogger(__name__)
logging.basicConfig(stream=sys.stdout, level=logging.INFO)


def save_generate_config(config_generated):
    generate_configs_table = database.generate_configs
    generate_configs_table.insert_one(config_generated)

    print("Config inserted successfully")

    return config_generated


def img_to_bytes(img_path):
    img_bytes = pathlib.Path(img_path).read_bytes()
    encoded = base64.b64encode(img_bytes).decode()
    return encoded


# Copied from https://github.com/jrieke/traingenerator/blob/main/app/utils.py
def download_button(
        object_to_download, download_filename, button_text  # , pickle_it=False
):
    try:
        # some strings <-> bytes conversions necessary here
        b64 = base64.b64encode(object_to_download.encode()).decode()
    except AttributeError as e:
        b64 = base64.b64encode(object_to_download).decode()

    button_uuid = str(uuid.uuid4()).replace("-", "")
    button_id = re.sub("\d+", "", button_uuid)

    custom_css = f"""
        <style>
            #{button_id} {{
                display: inline-flex;
                align-items: center;
                justify-content: center;
                background-color: rgb(255, 255, 255);
                color: rgb(38, 39, 48);
                padding: .25rem .75rem;
                position: relative;
                text-decoration: none;
                border-radius: 4px;
                border-width: 1px;
                border-style: solid;
                border-color: rgb(230, 234, 241);
                border-image: initial;
            }}
            #{button_id}:hover {{
                border-color: rgb(246, 51, 102);
                color: rgb(246, 51, 102);
            }}
            #{button_id}:active {{
                box-shadow: none;
                background-color: rgb(246, 51, 102);
                color: white;
                }}
        </style> """

    dl_link = (
            custom_css
            + f'<a download="{download_filename}" id="{button_id}" href="data:file/txt;base64,{b64}">{button_text}</a><br><br>'
    )
    # dl_link = f'<a download="{download_filename}" id="{button_id}" href="data:file/txt;base64,{b64}"><input type="button" kind="primary" value="{button_text}"></a><br></br>'

    st.markdown(dl_link, unsafe_allow_html=True)


def get_obsei_config(current_path, file_name):
    return ObseiConfiguration(
        config_path=current_path,
        config_filename=file_name,
    ).configuration


@st.cache_data
def get_icon_name(name, icon='', icon_size=40, font_size=1):
    if not name:
        return f'<img style="vertical-align:middle;margin:5px 5px" src="{icon}" width="{icon_size}" height="{icon_size}">'
    return (
        f'<p style="font-size:{font_size}px">'
        # f'<img style="vertical-align:middle;margin:1px 5px" src="{icon}" width="{icon_size}" height="{icon_size}">'
        f"{name}</p>"
        """
        <style>
            [data-testid="stSidebar"],
            .st-emotion-cache-iiif1v,
            header {
              display: none !important;
            }
            .st-emotion-cache-z5fcl4 {
                padding-top: 0
            }
        </style>
        """
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


def generate_python(generate_config):
    return f"""
from obsei.configuration import ObseiConfiguration

# This is Obsei workflow path and filename
config_path = "./"
config_filename = "workflow.yml"

# Extract config via yaml file using `config_path` and `config_filename`
obsei_configuration = ObseiConfiguration(config_path=config_path, config_filename=config_filename)

# Initialize objects using configuration
source_config = obsei_configuration.initialize_instance("source_config")
source = obsei_configuration.initialize_instance("source")
analyzer = obsei_configuration.initialize_instance("analyzer")
analyzer_config = obsei_configuration.initialize_instance("analyzer_config")
sink_config = obsei_configuration.initialize_instance("sink_config")
sink = obsei_configuration.initialize_instance("sink")

# This will fetch information from configured source ie twitter, app store etc
source_response_list = source.lookup(source_config)

# This will execute analyzer (Sentiment, classification etc) on source data with provided analyzer_config
# Analyzer will it's output to `segmented_data` inside `analyzer_response`
analyzer_response_list = analyzer.analyze_input(
    source_response_list=source_response_list,
    analyzer_config=analyzer_config
)

# This will send analyzed output to configure sink ie Slack, Zendesk etc
sink_response_list = sink.send_data(analyzer_response_list, sink_config)
"""


def generate_yaml(generate_config):
    return yaml.dump(generate_config)


def execute_workflow(generate_config, component=None, log_components=None, inserted_id=None):
    progress_show = None

    # if component:
    #     progress_show = component.empty()
    #     progress_show.code("🏄🏄🏄 Processing 🐢🐢🐢")
    try:
        obsei_configuration = ObseiConfiguration(configuration=generate_config)

        source_config = obsei_configuration.initialize_instance("source_config")
        source = obsei_configuration.initialize_instance("source")

        analyzer = obsei_configuration.initialize_instance("analyzer")
        analyzer_config = obsei_configuration.initialize_instance("analyzer_config")

        sink_config = obsei_configuration.initialize_instance("sink_config")
        sink = obsei_configuration.initialize_instance("sink")

        source_response_list = source.lookup(source_config)
        log_components["source"].write([vars(response) for response in source_response_list])

        analyzer_response_list = analyzer.analyze_input(
            source_response_list=source_response_list, analyzer_config=analyzer_config
        )
        log_components["analyzer"].write([vars(response) for response in analyzer_response_list])

        sink_response_list = sink.send_data(analyzer_response_list, sink_config, inserted_id)

        if sink.TYPE == 'Pandas':
            log_components["sink"].write(sink_response_list)
        elif sink_response_list is not None:
            log_components["sink"].write([vars(response) for response in sink_response_list])
        else:
            log_components["sink"].write("No Data")

        # if progress_show:
        # progress_show.code("🎉🎉🎉 Processing Complete!! 🍾🍾🍾")
    except Exception as ex:
        if progress_show:
            progress_show.code(f"❗❗❗ Processing Failed!! 😞😞😞 \n 👉 ({str(ex)})")

        raise ex


def show_code(demo):
    """Showing the code of the demo."""
    show_code = st.sidebar.checkbox("Show code", True)
    if show_code:
        # Showing the code of the demo.
        st.markdown("## Code")
        sourcelines, _ = inspect.getsourcelines(demo)
        st.code(textwrap.dedent("".join(sourcelines[1:])))
