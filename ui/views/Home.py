from ui.views.utils import *
from ui.socials.youtube import save_youtube_analyze
from ui.socials.play_app_store import save_analyze
from ui.socials.google_news import save_google_news_analyze
from ui.socials.crawler import save_crawler_analyze
from ui.socials.reddit_rss import save_reddit_rss_analyze
from ui.socials.tiktok import save_tiktok_analyze
from ui.socials.insta_facebook import save_meta_analyze
import sys

current_path = pathlib.Path(__file__).parent.absolute().as_posix()
configuration = get_obsei_config(current_path, "config.yaml")
logo_url = "https://raw.githubusercontent.com/obsei/obsei-resources/master/logos/obsei_200x200.png"

st.set_page_config(page_title="Social Listener", layout="wide", page_icon=logo_url,
                   initial_sidebar_state="collapsed"
                   )
st.title("Data Social Listener").markdown(
    get_icon_name("Social Listener", logo_url, 60, 35), unsafe_allow_html=True
)

columns_ui = [2, 2, 2]

(
    pipeline_col,
    spinner_col,
    execute_col,
) = st.columns(columns_ui)

col_map = dict()
col_map["source"], col_map["analyzer"], col_map["sink"] = st.columns([1, 1, 1])

selected = {}
name_map = {"source": "Platforms", "analyzer": "Analyzer", "sink": "Informer"}

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

execute_button = execute_col.button("🚀 Execute")
if execute_button:
    if spinner_col is None:
        sys.exit()

    progress_show = spinner_col.empty()
    progress_show.code("🏄🏄🏄 Processing 🐢🐢🐢")

    params = st.experimental_get_query_params()
    progress_show = check_system(generate_config, params, progress_show)
    data_informer = []
    print(generate_config)
    if generate_config['source']['target__'] == 'core.source.youtube_scrapper.YoutubeScrapperSource':
        data_informer = save_youtube_analyze(generate_config, progress_show)
    if (generate_config['source']['target__'] in
            ['core.source.appstore_scrapper.AppStoreScrapperSource',
             'core.source.playstore_scrapper.PlayStoreScrapperSource']):
        data_informer = save_analyze(generate_config, progress_show)
    if generate_config['source']['target__'] == 'core.source.google_news_source.GoogleNewsSource':
        data_informer = save_google_news_analyze(generate_config, progress_show)

    if generate_config['source']['target__'] == 'core.source.website_crawler_source.TrafilaturaCrawlerSource':
        data_informer = save_crawler_analyze(generate_config, progress_show)

    if generate_config['source']['target__'] == 'core.source.reddit_scrapper.RedditScrapperSource':
        data_informer = save_reddit_rss_analyze(generate_config, progress_show)

    if generate_config['source']['target__'] == 'core.source.tiktok_scrapper.TiktokScrapperSource':
        data_informer = save_tiktok_analyze(generate_config, progress_show)

    if (generate_config['source']['target__'] in
            ['core.source.facebook_scrapper.FacebookScrapperSource',
             'core.source.instagram_scrapper.InstagramScrapperSource']):
        data_informer = save_meta_analyze(generate_config, progress_show)

    if isinstance(data_informer, list):
        analyzer_response_list = data_informer[1]
        progress_show = data_informer[0]
        show_data_table(generate_config, log_component, analyzer_response_list, progress_show)
        if progress_show:
            progress_show.code("🎉🎉🎉 Processing Complete!! 🍾🍾🍾")

