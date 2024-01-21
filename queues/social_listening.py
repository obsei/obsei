from obsei.configuration import ObseiConfiguration
import pymongo, urllib
from pymongo import InsertOne
import datetime
from typing import Any, Dict, List, Optional
from obsei.payload import TextPayload
from obsei.misc.utils import flatten_dict

# from database import *
MONGO_DB = "obsei"
MONGO_USER = "root"
MONGO_PASS = "Aa@123456"

uri_mongo = "mongodb://" + MONGO_USER + ":" + urllib.parse.quote(MONGO_PASS) + "@localhost:27017/" + MONGO_DB
client = pymongo.MongoClient(uri_mongo)
database = client.obsei


def convert(
        analyzer_response: TextPayload,
        base_payload: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
) -> Dict[str, Any]:
    base_payload = base_payload or {}
    merged_dict = {**base_payload, **analyzer_response.to_dict()}
    return flatten_dict(merged_dict)


def execute_workflow(urls_table, generate_config):
    analyzer_response_list = []

    try:
        for record in urls_table:
            inserted_id = record["_id"]
            user_id = generate_config['user_id']
            if generate_config['source_config']['_target_'] in ['obsei.source.tiktok_scrapper.TiktokScrapperConfig', 'obsei.source.youtube_scrapper.YoutubeScrapperConfig']:
                generate_config['source_config']['video_url'] = record['url']
            if generate_config['source_config']['_target_'] in ['obsei.source.website_crawler_source.TrafilaturaCrawlerConfig']:
                generate_config['source_config']['urls'] = [record['url']]
            if generate_config['source_config']['_target_'] in ['obsei.source.google_news_source.GoogleNewsConfig']:
                generate_config['source_config']['query'] = record['keyword']
            if generate_config['source_config']['_target_'] in ['obsei.source.playstore_scrapper.PlayStoreScrapperConfig', 'obsei.source.appstore_scrapper.AppStoreScrapperConfig']:
                generate_config['source_config']['app_url'] = record['url']
            if generate_config['source_config']['_target_'] in ['obsei.source.reddit_scrapper.RedditScrapperConfig']:
                generate_config['source_config']['url'] = record['url']

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
    if record['source_name'] == 'YoutubeScrapper':
        save_analysis(record, 'meta_comment_id', bulk_operations)

    if record['source_name'] == 'AppStoreScrapper' or record['source_name'] == 'RedditScrapper':
        save_analysis(record, 'meta_id', bulk_operations)

    if record['source_name'] == 'PlayStoreScrapper':
        save_analysis(record, 'meta_reviewId', bulk_operations)

    if record['source_name'] == 'GoogleNews':
        save_analysis(record, 'meta_url', bulk_operations)

    if record['source_name'] == 'Crawler':
        save_analysis(record, 'meta_source', bulk_operations)

    if record['source_name'] == 'TiktokScrapper':
        save_analysis(record, 'meta_cid', bulk_operations)

    if record['source_name'] == 'FacebookScrapper':
        save_analysis(record, 'meta_comment_id', bulk_operations)

    # Execute bulk operations for non-existing records
    if bulk_operations:
        result = database.data_analyzed.bulk_write(bulk_operations)
        print("Inserted Count:", result.inserted_count)


def save_analysis(record, key, bulk_operations):
    if key not in record:
        return

    item = record[key]
    existing_record = database.data_analyzed.find_one({key: item})

    if existing_record is None:
        bulk_operations.append(InsertOne(record))
    else:
        database.data_analyzed.update_one({key: item}, {'$set': record})
        print(f"Skipped record: {item} (already exists)")
