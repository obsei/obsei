import base64

import streamlit as st
from PIL import Image

from obsei.configuration import ObseiConfiguration
import pathlib


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
def get_icon_name(name, icon, icon_size=30, font_size=25):
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
            text_data = component.text_area(f'Enter {" ".join(tokens)}', ", ".join(v))
            text_list = text_data.split(",")
            config[k] = [text.strip() for text in text_list]
        else:
            is_secret = tokens[-1] in ["key", "password", "token", "secret"]
            config[k] = component.text_input(f'Enter {" ".join(tokens)}', v, type="password" if is_secret else "default")

    print(config)


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


src_i, src_l, ana_i, ana_l, sink_i, sink_l = st.beta_columns([1, 5, 1, 5, 1, 5])

source_list = [k for k in obsei_config["source"].keys()]
selected_source = src_l.selectbox(
    "Select Observer/Source",
    source_list
)
src_icon = get_icon_name(None, obsei_config["source"][selected_source]["icon"])
src_i.header(selected_source).markdown(
    src_icon,
    unsafe_allow_html=True
)

analyzer_list = [k for k in obsei_config["analyzer"].keys()]
selected_analyzer = ana_l.selectbox(
    "Select Analyzer",
    analyzer_list
)
analyzer_icon = get_icon_name(None, obsei_config["analyzer"][selected_analyzer]["icon"])
ana_i.header(selected_analyzer).markdown(
    analyzer_icon,
    unsafe_allow_html=True
)

sink_list = [k for k in obsei_config["sink"].keys()]
selected_sink = sink_l.selectbox(
    "Select Informer/Sink",
    sink_list
)
sink_icon = get_icon_name(None, obsei_config["sink"][selected_sink]["icon"])
sink_i.header(selected_source).markdown(
    sink_icon,
    unsafe_allow_html=True
)

source_col, analyzer_col, sink_col = st.beta_columns([1, 1, 1])

src_config = obsei_config["source"][selected_source]["config"]
render_config(src_config, source_col)

analyzer_config = None if "config" not in obsei_config["analyzer"][selected_analyzer] else obsei_config["analyzer"][selected_analyzer]["config"]
render_config(analyzer_config, analyzer_col)

sink_config = obsei_config["sink"][selected_sink]["config"]
render_config(sink_config, sink_col)
