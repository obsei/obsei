import pymongo
from api.src.implement.interactor.singleton import Singleton
from api.src.setting import Settings

import urllib

settings = Settings()


class DatabaseConnector(metaclass=Singleton):
    def __init__(self):
        self.config = settings
        self.client = None
        self.db = None

    def connect(self):
        pw = urllib.parse.quote(self.config.db_password)
        uri_mongo = "mongodb://" + self.config.db_user + ":" + pw + "@" + self.config.db_host + ":" + self.config.db_port + self.config.db_name

        self.client = pymongo.MongoClient(uri_mongo)

        return self.client

