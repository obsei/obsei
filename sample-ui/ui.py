from utils import *

current_path = pathlib.Path(__file__).parent.absolute().as_posix()
configuration = get_obsei_config(current_path, "config.yaml")
logo_url = "https://raw.githubusercontent.com/obsei/obsei-resources/master/logos/obsei_200x200.png"

st.set_page_config(page_title="Obsei Demo", layout="wide", page_icon=logo_url)

st.title("Obsei Demo").markdown(
    get_icon_name("Obsei Demo", logo_url, 60, 35), unsafe_allow_html=True
)

st.error(
    """
**Note:** Demo run will require some secure information based on source or sink selected,
if you don't trust this environment please close the app.\n
Do not share and commit generated file as it may contains secure information.
"""
)

(
    pipeline_col,
    spinner_col,
    execute_col,
    download_python_col,
    download_yaml_col,
) = st.columns([2, 2, 1, 1, 1])

source_col, analyzer_col, sink_col = st.columns([1, 1, 1])

source_list = [k for k in configuration["source"].keys()]
selected_source = source_col.selectbox("Select Observer", source_list)

analyzer_list = [k for k in configuration["analyzer"].keys()]
selected_analyzer = analyzer_col.selectbox("Select Analyzer", analyzer_list)

sink_list = [k for k in configuration["sink"].keys()]
selected_sink = sink_col.selectbox("Select Informer", sink_list)

src_icon = get_icon_name(None, configuration["source"][selected_source]["_icon_"])
analyzer_icon = get_icon_name(
    None, configuration["analyzer"][selected_analyzer]["_icon_"]
)
sink_icon = get_icon_name(None, configuration["sink"][selected_sink]["_icon_"])
pipeline_col.header("Pipeline").markdown(
    f"**Pipeline:** {src_icon} ➡➡ {analyzer_icon} ➡➡ {sink_icon}",
    unsafe_allow_html=True,
)

src_config = configuration["source"][selected_source]["config"]
render_config(
    src_config, source_col, configuration["source"][selected_source]["_help_"]
)

analyzer_type_config = configuration["analyzer"][selected_analyzer]
analyzer_type_list = []
for k in analyzer_type_config.keys():
    if k != "_icon_":
        analyzer_type_list.append(k)
selected_analyzer_type = analyzer_col.selectbox(f"analyzer type", analyzer_type_list)
analyzer_config = None
if "config" in analyzer_type_config[selected_analyzer_type]:
    analyzer_config = analyzer_type_config[selected_analyzer_type]["config"]
render_config(
    analyzer_config,
    analyzer_col,
    analyzer_type_config[selected_analyzer_type]["_help_"],
)
if len(analyzer_type_config[selected_analyzer_type]["analyzer"]) > 1:
    render_config(
        analyzer_type_config[selected_analyzer_type]["analyzer"], analyzer_col
    )

sink_config = configuration["sink"][selected_sink]["config"]
render_config(sink_config, sink_col, configuration["sink"][selected_sink]["_help_"])

generate_config = {
    "source": configuration["source"][selected_source]["source"],
    "source_config": src_config,
    "analyzer_config": analyzer_config,
    "analyzer": analyzer_type_config[selected_analyzer_type]["analyzer"],
    "sink": configuration["sink"][selected_sink]["sink"],
    "sink_config": sink_config,
}

python_code = generate_python(generate_config)
yaml_code = generate_yaml(generate_config)

execute_button = execute_col.button("🚀 Execute")
if execute_button:
    execute_workflow(generate_config, spinner_col)

with download_python_col:
    download_button(python_code, "generated-code.py", "🐍 Download (.py)")

with download_yaml_col:
    download_button(yaml_code, "generated-config.yaml", "📖 Download (.yaml)")
