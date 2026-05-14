import json
import os
import socket
import sys
from pathlib import Path

import redis
from dotenv import load_dotenv

sys.path.append(str(Path(__file__).resolve().parents[1]))

from workers.celery_config import celery_app


def get_redis_url() -> str:
    redis_url = os.getenv("REDIS_URL")
    if not redis_url:
        raise RuntimeError("REDIS_URL environment variable is not set")
    return redis_url


def localhost_redis_url(redis_url: str) -> str:
    return redis_url.replace("@redis:", "@localhost:", 1).replace(
        "://redis:",
        "://localhost:",
        1,
    )


def resolve_redis_url(redis_url: str) -> str:
    try:
        client = redis.Redis.from_url(redis_url, decode_responses=True)
        client.ping()
        return redis_url
    except redis.ConnectionError as exc:
        if "@redis:" not in redis_url and "://redis:" not in redis_url:
            raise
        local_redis_url = localhost_redis_url(redis_url)
        try:
            client = redis.Redis.from_url(local_redis_url, decode_responses=True)
            client.ping()
            return local_redis_url
        except (redis.ConnectionError, socket.gaierror):
            raise exc


def connect_redis(redis_url: str) -> redis.Redis:
    return redis.Redis.from_url(redis_url, decode_responses=True)


def count_pending_tasks(client: redis.Redis) -> int:
    return client.llen("celery")


def count_active_tasks() -> int:
    inspector = celery_app.control.inspect()
    active = inspector.active() or {}
    return sum(len(tasks) for tasks in active.values())


def count_failed_tasks(client: redis.Redis) -> int:
    failed = 0
    for key in client.scan_iter("celery-task-meta-*"):
        value = client.get(key)
        if not value:
            continue
        try:
            payload = json.loads(value)
        except json.JSONDecodeError:
            continue
        if payload.get("status") == "FAILURE":
            failed += 1
    return failed


def main() -> None:
    load_dotenv()

    redis_url = resolve_redis_url(get_redis_url())
    celery_app.conf.update(broker_url=redis_url, result_backend=redis_url)
    client = connect_redis(redis_url)
    print(f"pending_tasks={count_pending_tasks(client)}")
    print(f"active_tasks={count_active_tasks()}")
    print(f"failed_tasks={count_failed_tasks(client)}")


if __name__ == "__main__":
    main()
