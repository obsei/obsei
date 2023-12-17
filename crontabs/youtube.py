#!/usr/bin/python3
# -*- coding: utf-8 -*-

import pymongo
import urllib
from bson import ObjectId
from obsei.configuration import ObseiConfiguration

MONGO_HOST = "localhost"
MONGO_PORT = "27017"
MONGO_DB = "obsei"
MONGO_USER = "root"
MONGO_PASS = "Aa@123456"

uri_mongo = "mongodb://" + MONGO_USER + ":" + urllib.parse.quote(MONGO_PASS) + "@localhost:27017/" + MONGO_DB
client = pymongo.MongoClient(uri_mongo)
database = client.obsei


def get_generate_config():
    results = database.generate_configs.find()
    return results


def get_list_urls(config_id):
    results = database.urls.find({'generated_config_id': ObjectId(config_id)})
    return results


def execute_workflow(generate_config, inserted_id=None):
    obsei_configuration = ObseiConfiguration(configuration=generate_config)

    source_config = obsei_configuration.initialize_instance("source_config")
    source = obsei_configuration.initialize_instance("source")

    analyzer = obsei_configuration.initialize_instance("analyzer")
    analyzer_config = obsei_configuration.initialize_instance("analyzer_config")

    sink_config = obsei_configuration.initialize_instance("sink_config")
    sink = obsei_configuration.initialize_instance("sink")

    source_response_list = source.lookup(source_config)

    analyzer_response_list = analyzer.analyze_input(
        source_response_list=source_response_list, analyzer_config=analyzer_config
    )

    sink.send_data(analyzer_response_list, sink_config, inserted_id)


def execute_youtube():
    results = get_generate_config()

    for result in results:
        urls_table = get_list_urls(result['_id'])
        for record in urls_table:
            result['source_config']['video_url'] = record['url']
            execute_workflow(result, record["_id"])


if __name__ == '__main__':
    execute_youtube()
