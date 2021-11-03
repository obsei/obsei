from utils import *

current_path = pathlib.Path(__file__).parent.absolute().as_posix()
configuration = get_obsei_config(current_path, "config.yaml")
logo_url = "https://raw.githubusercontent.com/obsei/obsei-resources/master/logos/obsei_200x200.png"

st.set_page_config(page_title="Obsei Demo", layout="wide", page_icon=logo_url)

st.title("Obsei Demo").markdown(
    get_icon_name("Obsei Demo", logo_url, 60, 35), unsafe_allow_html=True
)

st.success(
    """
Please ⭐ the repo and share the feedback at https://github.com/obsei/obsei
    """
)
st.warning(
    """
**Note:** Demo run will require some secure information based on source or sink selected,
if you don't trust this environment please close the app.
"""
)

(
    pipeline_col,
    spinner_col,
    execute_col,
    download_python_col,
    download_yaml_col,
) = st.columns([2, 2, 1, 1, 1])

col_map = dict()
col_map["source"], col_map["analyzer"], col_map["sink"] = st.columns([1, 1, 1])

selected = {}
name_map = {"source": "Observer", "analyzer": "Analyzer", "sink": "Informer"}

for node_name, col in col_map.items():
    item_list = [k for k in configuration[node_name].keys()]
    selected[node_name] = col.selectbox(f"Select {name_map[node_name]}", item_list)

icons = [get_icon_name(None, configuration[k][v]["_icon_"]) for k, v in selected.items()]
pipeline_col.header("Pipeline").markdown(
    f"**Pipeline:** {icons[0]} ➡➡ {icons[1]} ➡➡ {icons[2]}",
    unsafe_allow_html=True,
)

generate_config = {}
log_component = {}
for node_name, node_value in selected.items():
    type_config = configuration[node_name][node_value]
    if node_name == "analyzer":
        type_list = []
        for config_key in type_config.keys():
            if config_key != "_icon_":
                type_list.append(config_key)
        selected_type = col_map[node_name].selectbox(f"{name_map[node_name]} Type", type_list)
        type_config = type_config[selected_type]

    config = None
    if "config" in type_config:
        config = type_config["config"]
        if type_config["_help_"] is not None:
            with col_map[node_name].expander("Config Help Info", False):
                help_area = "\n".join(type_config["_help_"])
                st.code(f"{help_area}")

    config_expander = None
    if config is not None:
        config_expander = col_map[node_name].expander(f"Configure {name_map[node_name]}", False)
        render_config(config, config_expander)

    if node_name == "analyzer" and node_name in type_config and len(type_config[node_name]) > 1:
        config_expander = config_expander or col_map[node_name].expander(f"Configure {name_map[node_name]}", False)
        render_config(type_config["analyzer"], config_expander)

    generate_config[node_name] = type_config[node_name]
    generate_config[f"{node_name}_config"] = config

    log_expander = col_map[node_name].expander(f"{name_map[node_name]} Logs", False)
    log_component[node_name] = log_expander.empty()
    log_component[node_name].write("Run \"🚀 Execute\" first")

python_code = generate_python(generate_config)
yaml_code = generate_yaml(generate_config)

execute_button = execute_col.button("🚀 Execute")
if execute_button:
    execute_workflow(generate_config, spinner_col, log_component)

with download_python_col:
    download_button(python_code, "generated-code.py", "🐍 Download (.py)")

with download_yaml_col:
    download_button(yaml_code, "generated-config.yaml", "📖 Download (.yaml)")
