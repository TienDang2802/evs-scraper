import os

import redis
from rq import Worker, Queue, Connection

listen = ['high', 'default', 'low']

redis_host = os.getenv('REDIS_HOST', 'localhost')
redis_url = 'redis://{redis_host}:{redis_post}'.format(redis_host=redis_host,redis_post=os.getenv('REDIS_PORT', 6379))

conn = redis.from_url(redis_url)

if __name__ == '__main__':
    with Connection(conn):
        worker = Worker(map(Queue, listen))
        worker.work()
