from core.configuration import ObseiConfiguration
from pymongo import InsertOne
import datetime
from typing import Any, Dict, Optional
from core.payload import TextPayload
from core.misc.utils import flatten_dict
from bson import ObjectId
from database import *


def execute_workflow(config_id: str, start: False):
    if start is False:
        return

    generate_config = database.generate_configs.find_one(ObjectId(config_id))
    keys_to_rename = ['source', 'source_config', 'analyzer', 'analyzer_config', 'sink', 'sink_config']
    for key in keys_to_rename:
        if key in generate_config:
            generate_config[key]['_target_'] = generate_config[key].pop('target__')

    urls = database.urls.find({'generated_config_id': config_id})
    analyzer_response_list = []

    try:
        for record in urls:
            inserted_id = record['_id']
            user_id = generate_config['user_id']
            target_mappings = {
                'core.source.tiktok_scrapper.TiktokScrapperConfig': {'video_url': record['url']},
                'core.source.youtube_scrapper.YoutubeScrapperConfig': {'video_url': record['url']},
                'core.source.website_crawler_source.TrafilaturaCrawlerConfig': {'urls': [record['url']]},
                'core.source.playstore_scrapper.PlayStoreScrapperConfig': {'app_url': record['url']},
                'core.source.appstore_scrapper.AppStoreScrapperConfig': {'app_url': record['url']},
                'core.source.reddit_scrapper.RedditScrapperConfig': {'url': record['url']},
                'core.source.facebook_scrapper.FacebookScrapperConfig': {'urls': record['url']},
                'core.source.instagram_scrapper.InstagramScrapperConfig': {'urls': record['url']}
            }

            if 'keyword' in record:
                target_mappings['core.source.google_news_source.GoogleNewsConfig'] = {'query': record['keyword']}

            if generate_config['source_config']['_target_'] in target_mappings:
                generate_config['source_config'].update(target_mappings[generate_config['source_config']['_target_']])

            obsei_configuration = ObseiConfiguration(configuration=generate_config)

            source_config = obsei_configuration.initialize_instance("source_config")
            source = obsei_configuration.initialize_instance("source")

            analyzer = obsei_configuration.initialize_instance("analyzer")
            analyzer_config = obsei_configuration.initialize_instance("analyzer_config")

            source_response_list = source.lookup(source_config)

            analyzer_response_list = analyzer.analyze_input(
                source_response_list=source_response_list, analyzer_config=analyzer_config
            )

            for analyzer_response in analyzer_response_list:
                converted_response = convert(
                    analyzer_response=analyzer_response
                )
                response: Optional[Dict[str, Any]]
                response = converted_response

                response['created_at'] = datetime.datetime.now()
                if inserted_id is not None:
                    response['url_id'] = inserted_id

                if user_id is not None:
                    response['user_id'] = user_id

                prepare_data_analysis(response)
    except Exception as ex:
        raise ex

    return analyzer_response_list


def prepare_data_analysis(record):
    bulk_operations = []
    source_meta_mapping = {
        'AppStoreScrapper': 'meta_reviewId',
        'RedditScrapper': 'meta_id',
        'PlayStoreScrapper': 'meta_reviewId',
        'GoogleNews': 'meta_url',
        'Crawler': 'meta_source',
        'TiktokScrapper': 'meta_cid',
        'FacebookScrapper': 'meta_comment_id',
        'InstagramScrapper': 'meta_comment_id',
        'YoutubeScrapper': 'meta_comment_id'
    }

    for source_name, meta_key in source_meta_mapping.items():
        if record['source_name'] == source_name:
            save_analysis(record, meta_key, bulk_operations)
            break

    if bulk_operations:
        result = database.data_analyzed.bulk_write(bulk_operations)
        print("Inserted Count:", result.inserted_count)


def save_analysis(record, key, bulk_operations):
    if key not in record:
        return

    item = record[key]
    existing_record = database.data_analyzed.find_one({key: item})
    if 'segmented_data_ner_data_score' in record:
        import numpy as np
        record['segmented_data_ner_data_score'] = float(np.float32(record['segmented_data_ner_data_score']))

    if existing_record is None:
        bulk_operations.append(InsertOne(record))
    else:
        database.data_analyzed.update_one({key: item}, {'$set': record})
        print(f"Skipped record: {item} (already exists)")


def convert(
        analyzer_response: TextPayload,
        base_payload: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
) -> Dict[str, Any]:
    base_payload = base_payload or {}
    merged_dict = {**base_payload, **analyzer_response.to_dict()}
    return flatten_dict(merged_dict)


