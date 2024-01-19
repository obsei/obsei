from rq import Queue
from redis import Redis
from test_job import count_words_at_url
import time

# Tell RQ what Redis connection to use
redis_conn = Redis()
q = Queue(connection=redis_conn)  # no args implies the default queue

# Delay execution of count_words_at_url('http://nvie.com')
job = q.enqueue(count_words_at_url,
                args=(
                    111111, 'http://nvie.com'
                ))
print(job.result)   # => None  # Changed to job.return_value() in RQ >= 1.12.0

# Now, wait a while, until the worker is finished
time.sleep(2)
print(job.result)