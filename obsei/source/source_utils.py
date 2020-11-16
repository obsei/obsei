from typing import Any, Dict

from obsei.source.twitter_source import TwitterSource, TwitterSourceConfig

source_map = {
    "Twitter": {
        "config": TwitterSourceConfig,
        "source": TwitterSource(),
    },
}


def source_config_from_dict(source_type: str, config: Dict[str, Any]):
    return source_map[source_type]["source"], source_map[source_type]["config"].from_dict(config)
