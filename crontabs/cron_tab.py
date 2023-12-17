from crontab import CronTab
import subprocess
import pymongo
import urllib

SERVER_USERNAME = 'vcontent-listener'

# from database import *
MONGO_DB = "obsei"
MONGO_USER = "root"
MONGO_PASS = "Aa@123456"

uri_mongo = "mongodb://" + MONGO_USER + ":" + urllib.parse.quote(MONGO_PASS) + "@localhost:27017/" + MONGO_DB
client = pymongo.MongoClient(uri_mongo)
database = client.obsei

cron = CronTab(user=SERVER_USERNAME)

command = "python3 python/obsei/crontabs/youtube.py  >> out.txt  2>&1"
result = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
output = result.stdout


COMAND_DEFINED = 'python3 /htdocs/listener.vcontent.info/crontabs/youtube.py >> out.txt  2>&1 # youtube scrapper'
COMAND_LOCAL_DEFINED = 'python3 python/obsei/crontabs/youtube.py >> out.txt  2>&1 # youtube scrapper'

if command in output:
    print("The command is present in the crontab.")
    for job in cron:
        if job.comment == 'youtube scrapper':
            database.crontabs.update_one({
                'command': COMAND_DEFINED,
            }, {'$set': {
                'type': 'minute',
                'time': 100
            }})

            job.minute.every(100)
            cron.write()

            print('Cron job modified successfully')

else:
    print("The command is not found in the crontab. Inserted")
    database.crontabs.insert_one({
        'command': COMAND_DEFINED,
        'type': 'minute',
        'time': 10
    })
    job = cron.new(command=COMAND_DEFINED)
    job.minute.every(10)
    job.enable()
    cron.write()
