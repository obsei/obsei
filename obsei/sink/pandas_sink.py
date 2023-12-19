from typing import Any, Dict, List, Optional
from pandas import DataFrame, concat
from obsei.payload import TextPayload
from obsei.misc.utils import flatten_dict
from obsei.sink.base_sink import BaseSink, BaseSinkConfig, Convertor
import pymongo
from pymongo import InsertOne
import urllib
import datetime

now = datetime.datetime.now()

# from database import *
MONGO_DB = "obsei"
MONGO_USER = "root"
MONGO_PASS = "Aa@123456"

uri_mongo = "mongodb://" + MONGO_USER + ":" + urllib.parse.quote(MONGO_PASS) + "@localhost:27017/" + MONGO_DB
client = pymongo.MongoClient(uri_mongo)
database = client.obsei


class PandasConvertor(Convertor):
    def convert(
            self,
            analyzer_response: TextPayload,
            base_payload: Optional[Dict[str, Any]] = None,
            **kwargs: Any,
    ) -> Dict[str, Any]:
        base_payload = base_payload or {}
        merged_dict = {**base_payload, **analyzer_response.to_dict()}
        return flatten_dict(merged_dict)


class PandasSinkConfig(BaseSinkConfig):
    TYPE: str = "Pandas"
    dataframe: Optional[DataFrame] = None
    # By default, it will include all the columns
    include_columns_list: Optional[List[str]] = None

    def __init__(self, **data: Any):
        super().__init__(**data)
        self.dataframe = self.dataframe or DataFrame()


class PandasSink(BaseSink):
    TYPE: str = "Pandas"

    def __init__(self, convertor: Convertor = PandasConvertor(), **data: Any):
        super().__init__(convertor=convertor, **data)

    def send_data(
            self,
            analyzer_responses: List[TextPayload],
            config: PandasSinkConfig,
            inserted_id=None,
            user_id=None

    ) -> Any:
        responses = []
        for analyzer_response in analyzer_responses:
            converted_response = self.convertor.convert(
                analyzer_response=analyzer_response
            )
            response: Optional[Dict[str, Any]]
            if config.include_columns_list:
                response = {k: v for k, v in converted_response.items() if k in config.include_columns_list}
            else:
                response = converted_response

            response['created_at'] = now
            if inserted_id is not None:
                response['url_id'] = inserted_id

            if user_id is not None:
                response['user_id'] = user_id

            responses.append(response)

        if len(responses) > 0:
            bulk_operations = []

            database.data_analyzed.create_index([('processed_text', pymongo.TEXT), ], name='text_index')

            for record in responses:
                meta_comment_id = record['meta_comment_id']
                existing_record = database.data_analyzed.find_one({'meta_comment_id': meta_comment_id})

                if existing_record is None:
                    bulk_operations.append(InsertOne(record))
                else:
                    database.data_analyzed.update_one({'meta_comment_id': meta_comment_id}, {'$set': record})
                    print(f"Skipped record: {meta_comment_id} (already exists)")

            # Execute bulk operations for non-existing records
            if bulk_operations:
                result = database.data_analyzed.bulk_write(bulk_operations)
                print("Inserted Count:", result.inserted_count)

        if config.dataframe is not None:
            responses_df = DataFrame(responses)
            config.dataframe = concat([config.dataframe, responses_df], ignore_index=True)

        return config.dataframe
