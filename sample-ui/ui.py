import base64
import json
import re
import uuid

import streamlit as st
from PIL import Image

from obsei.configuration import ObseiConfiguration
import pathlib


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


def img_to_bytes(img_path):
    img_bytes = pathlib.Path(img_path).read_bytes()
    encoded = base64.b64encode(img_bytes).decode()
    return encoded


current_path = pathlib.Path(__file__).parent.absolute().as_posix()
obsei_config = ObseiConfiguration(
    config_path=current_path,
    config_filename="config.yaml",
).configuration


@st.cache
def get_icon_name(name, icon, icon_size=50, font_size=25):
    if not name:
        return f'<img style="vertical-align:middle;margin:5px 5px" src="{icon}" width="{icon_size}" height="{icon_size}">'
    return f'<p style="font-size:{font_size}px">' \
           f'<img style="vertical-align:middle;margin:1px 5px" src="{icon}" width="{icon_size}" height="{icon_size}">' \
           f'{name}</p>'


def render_config(config, component):
    if config is None:
        return
    for k, v in config.items():
        if k == "_target_":
            continue

        tokens = k.split("_")
        if isinstance(v, dict):
            render_config(v, component)
        elif isinstance(v, list):
            text_data = component.text_area(f'{" ".join(tokens)}', ", ".join(v), help="Comma separated list")
            text_list = text_data.split(",")
            config[k] = [text.strip() for text in text_list]
        elif isinstance(v, bool):
            options = [True, False]
            selected_option = component.radio(f'{" ".join(tokens)}', options, options.index(v))
            config[k] = bool(selected_option)
        else:
            is_secret = tokens[-1] in ["key", "password", "token", "secret"]
            hint = "Enter value" if "lookup" not in tokens else "Format: `<number><d|h|m>` d=day, h=hour & m=minute"
            config[k] = component.text_input(
                f'{" ".join(tokens)}', v,
                type="password" if is_secret else "default",
                help=hint
            )

    # print(config)


favicon = Image.open(f"{current_path}/../images/logos/obsei_200x200.png")
st.set_page_config(
    page_title="Obsei Demo",
    layout="wide",
    page_icon=favicon
)

st.title("Obsei Demo").markdown(
    get_icon_name(
        "Obsei Demo",
        "https://raw.githubusercontent.com/lalitpagaria/obsei/master/images/logos/obsei_200x200.png",
        50,
        25
    ),
    unsafe_allow_html=True
)

st.error('''
**Note:** Demo run will require some secure information based on source or sink selected,
if you don't trust this environment please close the app.\n
Do not share and commit generated file as it may contains secure information.
'''
         )

pipeline_col, filler1, col1, col2 = st.beta_columns([3, 1, 1, 1])

source_col, analyzer_col, sink_col = st.beta_columns([1, 1, 1])

source_list = [k for k in obsei_config["source"].keys()]
selected_source = source_col.selectbox(
    "Select Observer/Source",
    source_list
)

analyzer_list = [k for k in obsei_config["analyzer"].keys()]
selected_analyzer = analyzer_col.selectbox(
    "Select Analyzer",
    analyzer_list
)

sink_list = [k for k in obsei_config["sink"].keys()]
selected_sink = sink_col.selectbox(
    "Select Informer/Sink",
    sink_list
)

src_icon = get_icon_name(None, obsei_config["source"][selected_source]["_icon_"])
analyzer_icon = get_icon_name(None, obsei_config["analyzer"][selected_analyzer]["_icon_"])
sink_icon = get_icon_name(None, obsei_config["sink"][selected_sink]["_icon_"])
pipeline_col.header("Pipeline").markdown(
    f'**Pipeline:** {src_icon} ➡ {analyzer_icon} ➡ {sink_icon}',
    unsafe_allow_html=True
)

src_config = obsei_config["source"][selected_source]["config"]
render_config(src_config, source_col)

analyzer_type_config = obsei_config["analyzer"][selected_analyzer]
analyzer_type_list = []
for k in analyzer_type_config.keys():
    if k != "_icon_":
        analyzer_type_list.append(k)
selected_analyzer_type = analyzer_col.selectbox(
    f"analyzer type",
    analyzer_type_list
)
analyzer_config = None
if "config" in analyzer_type_config[selected_analyzer_type]:
    analyzer_config = analyzer_type_config[selected_analyzer_type]["config"]
render_config(analyzer_config, analyzer_col)

sink_config = obsei_config["sink"][selected_sink]["config"]
render_config(sink_config, sink_col)

generate_config = {
    "source": obsei_config["source"][selected_source]["source"],
    "source_config": src_config,
    "analyzer_config": analyzer_config,
    "analyzer": analyzer_type_config[selected_analyzer_type]["analyzer"],
    "sink": obsei_config["sink"][selected_sink]["sink"],
    "sink_config": sink_config,
}

python_code = f'''
import logging
import sys
import json

from obsei.configuration import ObseiConfiguration

logger = logging.getLogger(__name__)
logging.basicConfig(stream=sys.stdout, level=logging.INFO)

configuration = {json.dumps(generate_config, indent=2, sort_keys=True)}

obsei_configuration = ObseiConfiguration(configuration=json.load(configuration))

source_config = obsei_configuration.initialize_instance("source_config")
source = obsei_configuration.initialize_instance("source")
analyzer = obsei_configuration.initialize_instance("analyzer")
analyzer_config = obsei_configuration.initialize_instance("analyzer_config")
sink_config = obsei_configuration.initialize_instance("sink_config")
sink = obsei_configuration.initialize_instance("sink")

# This will fetch information from configured source ie twitter, app store etc
source_response_list = source.lookup(source_config)

# Uncomment if you want to log source response
# for idx, source_response in enumerate(source_response_list):
#     logger.info(f"source_response#'{{idx}}'='{{source_response.__dict__}}'")

# This will execute analyzer (Sentiment, classification etc) on source data with provided analyzer_config
analyzer_response_list = text_analyzer.analyze_input(
    source_response_list=source_response_list,
    analyzer_config=analyzer_config
)

# Uncomment if you want to log analyzer response
# for idx, an_response in enumerate(analyzer_response_list):
#    logger.info(f"analyzer_response#'{{idx}}'='{{an_response.__dict__}}'")

# Analyzer output added to segmented_data
# Uncomment inorder to log it
# for idx, an_response in enumerate(analyzer_response_list):
#    logger.info(f"analyzed_data#'{{idx}}'='{{an_response.segmented_data.__dict__}}'")

# This will send analyzed output to configure sink ie Slack, Zendesk etc
sink_response_list = sink.send_data(analyzer_response_list, sink_config)

# Uncomment if you want to log sink response
# for sink_response in sink_response_list:
#     if sink_response is not None:
#         logger.info(f"sink_response='{{sink_response/}}'")
'''

# yaml_code = yaml.dump(generate_config)

execute_button = col1.button("💻 Execute")  # logic handled further down
with col2:
    download_button(python_code, "generated-code.py", "🐍 Download (.py)")
