import logging
from collections.abc import Iterator
from contextlib import contextmanager

from django.conf import settings
from redis import Redis
from redis.exceptions import RedisError

from vstu_schedule.tasks.descriptors import (
    TASK_CONCURRENCY_PARALLEL,
    get_task_descriptor,
)

logger = logging.getLogger(__name__)

_ACTIVE_KEY = "vstu_schedule:celery_tasks:active"
_EXCLUSIVE_KEY = "vstu_schedule:celery_tasks:exclusive"
_SINGLETON_PREFIX = "vstu_schedule:celery_tasks:singleton:"
_DEFAULT_LOCK_TTL_SECONDS = 6 * 60 * 60

_ACQUIRE_SCRIPT = """
local mode = ARGV[1]
local task_name = ARGV[2]
local run_id = ARGV[3]
local ttl = tonumber(ARGV[4])
local singleton_key = KEYS[3] .. task_name

if mode == "parallel" then
    if redis.call("exists", KEYS[2]) == 1 then
        return 0
    end
elseif mode == "singleton" then
    if redis.call("exists", KEYS[2]) == 1 or redis.call("exists", singleton_key) == 1 then
        return 0
    end
    redis.call("set", singleton_key, run_id, "EX", ttl)
elseif mode == "exclusive" then
    if redis.call("exists", KEYS[2]) == 1 or redis.call("hlen", KEYS[1]) > 0 then
        return 0
    end
    redis.call("set", KEYS[2], run_id, "EX", ttl)
else
    return 0
end

redis.call("hset", KEYS[1], run_id, task_name)
redis.call("expire", KEYS[1], ttl)
return 1
"""

_RELEASE_SCRIPT = """
local mode = ARGV[1]
local task_name = ARGV[2]
local run_id = ARGV[3]
local singleton_key = KEYS[3] .. task_name

redis.call("hdel", KEYS[1], run_id)
if mode == "singleton" and redis.call("get", singleton_key) == run_id then
    redis.call("del", singleton_key)
end
if mode == "exclusive" and redis.call("get", KEYS[2]) == run_id then
    redis.call("del", KEYS[2])
end
return 1
"""


def _redis_client() -> Redis:
    return Redis.from_url(settings.CELERY_BROKER_URL, decode_responses=True)


def _task_concurrency(task_name: str) -> str:
    descriptor = get_task_descriptor(task_name)
    if descriptor is None:
        return TASK_CONCURRENCY_PARALLEL
    return descriptor.concurrency


def _lock_ttl_seconds(task_name: str) -> int:
    descriptor = get_task_descriptor(task_name)
    if descriptor and descriptor.time_limit_seconds:
        return max(descriptor.time_limit_seconds + 60, 60)
    return _DEFAULT_LOCK_TTL_SECONDS


@contextmanager
def celery_task_concurrency_lock(task_name: str, run_id: str | None) -> Iterator[bool]:
    """Apply descriptor concurrency policy for a Celery task execution."""
    descriptor = get_task_descriptor(task_name)
    if descriptor and descriptor.internal:
        yield True
        return

    mode = _task_concurrency(task_name)
    task_run_id = run_id or f"{task_name}:unknown"
    client = _redis_client()
    keys = [_ACTIVE_KEY, _EXCLUSIVE_KEY, _SINGLETON_PREFIX]

    try:
        acquired = bool(
            client.eval(
                _ACQUIRE_SCRIPT,
                len(keys),
                *keys,
                mode,
                task_name,
                task_run_id,
                _lock_ttl_seconds(task_name),
            )
        )
    except RedisError:
        logger.warning("Could not acquire Celery concurrency lock: %s", task_name, exc_info=True)
        raise

    if not acquired:
        logger.warning(
            "Task skipped by concurrency policy: %s [mode=%s, id=%s]",
            task_name,
            mode,
            task_run_id,
        )
        yield False
        return

    try:
        yield True
    finally:
        try:
            client.eval(_RELEASE_SCRIPT, len(keys), *keys, mode, task_name, task_run_id)
        except RedisError:
            logger.warning(
                "Could not release Celery concurrency lock: %s", task_name, exc_info=True
            )
