from utils import *
from socials.youtube import save_youtube_analyze
from socials.play_app_store import save_analyze
from socials.google_news import save_google_news_analyze
from socials.crawler import save_crawler_analyze
from socials.reddit_rss import save_reddit_rss_analyze
import sys

current_path = pathlib.Path(__file__).parent.absolute().as_posix()
configuration = get_obsei_config(current_path, "config.yaml")
logo_url = "https://raw.githubusercontent.com/obsei/obsei-resources/master/logos/obsei_200x200.png"

st.set_page_config(page_title="Social Listener", layout="wide", page_icon=logo_url, initial_sidebar_state="collapsed")
st.title("Data Social Listener").markdown(
    get_icon_name("Social Listener", logo_url, 60, 35), unsafe_allow_html=True
)

columns_ui = [2, 2, 2]
# columns_ui = [2, 2, 1, 1, 1]

(
    pipeline_col,
    spinner_col,
    execute_col,
    # download_python_col,
    # download_yaml_col,
) = st.columns(columns_ui)

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

    log_expander = col_map[node_name].expander(f"{name_map[node_name]} Logs", True)
    log_component[node_name] = log_expander.empty()
    log_component[node_name].write("Run \"🚀 Execute\" first")

python_code = generate_python(generate_config)
yaml_code = generate_yaml(generate_config)

execute_button = execute_col.button("🚀 Execute")
if execute_button:
    if spinner_col is None:
        sys.exit()

    progress_show = spinner_col.empty()
    progress_show.code("🏄🏄🏄 Processing 🐢🐢🐢")

    params = st.experimental_get_query_params()
    progress_show = check_system(generate_config, params, progress_show)

    if generate_config['source']['_target_'] == 'obsei.source.youtube_scrapper.YoutubeScrapperSource':
        progress_show = save_youtube_analyze(generate_config, log_component, progress_show)

    if generate_config['source']['_target_'] == 'obsei.source.appstore_scrapper.AppStoreScrapperSource' or \
            generate_config['source']['_target_'] == 'obsei.source.playstore_scrapper.PlayStoreScrapperSource':
        progress_show = save_analyze(generate_config, log_component, progress_show)

    if generate_config['source']['_target_'] == 'obsei.source.google_news_source.GoogleNewsSource':
        progress_show = save_google_news_analyze(generate_config, log_component, progress_show)

    if generate_config['source']['_target_'] == 'obsei.source.website_crawler_source.TrafilaturaCrawlerSource':
        progress_show = save_crawler_analyze(generate_config, log_component, progress_show)

    if generate_config['source']['_target_'] == 'obsei.source.reddit_scrapper.RedditScrapperSource':
        progress_show = save_reddit_rss_analyze(generate_config, log_component, progress_show)

    else:
        execute_workflow(generate_config, log_component, None, None, progress_show)

    if progress_show:
        progress_show.code("🎉🎉🎉 Processing Complete!! 🍾🍾🍾")
