import pymongo
import urllib

# Replace these with your server details
MONGO_HOST = "localhost"
MONGO_PORT = "27017"
MONGO_DB = "obsei"
MONGO_USER = "root"
MONGO_PASS = "Aa@123456"

uri_mongo = "mongodb://" + MONGO_USER + ":" + urllib.parse.quote(MONGO_PASS) + "@localhost:27017/"+ MONGO_DB
client = pymongo.MongoClient(uri_mongo)
database = client.obsei