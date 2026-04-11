"""Redis storage - members, reports, build records."""

import json
import logging
from datetime import datetime
from functools import wraps

import redis

from bot.config import KV_REDIS_URL, VN_TZ
from bot.constants import (
    KEY_MEMBERS, KEY_REPORT_PREFIX, KEY_BUILD_AUTH, KEY_BUILD_COUNTER, KEY_BUILD_PREFIX,
    TTL_REPORT, TTL_BUILD_RECORD, REDIS_TIMEOUT,
)

logger = logging.getLogger("bot.store")

try:
    db = redis.from_url(KV_REDIS_URL, socket_timeout=REDIS_TIMEOUT) if KV_REDIS_URL else None
except Exception as e:
    logger.error(f"Redis connection failed: {e}")
    db = None


def _with_redis(default):
    """Decorator: nếu Redis down, trả default. Catch RedisError."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            if not db:
                return default
            try:
                return func(*args, **kwargs)
            except redis.RedisError as e:
                logger.warning(f"{func.__name__} redis error: {e}")
                return default
        return wrapper
    return decorator


def _today_key() -> str:
    today = datetime.now(VN_TZ).strftime("%Y-%m-%d")
    return f"{KEY_REPORT_PREFIX}:{today}"


# ============ MEMBERS ============

@_with_redis({})
def kv_get() -> dict:
    data = db.get(KEY_MEMBERS)
    return json.loads(data) if data else {}


@_with_redis(None)
def kv_set(members: dict) -> None:
    db.set(KEY_MEMBERS, json.dumps(members))


# ============ REPORTS (Redis Hash - atomic) ============

@_with_redis({})
def get_today_reports() -> dict:
    data = db.hgetall(_today_key())
    return {k.decode(): json.loads(v) for k, v in data.items()} if data else {}


@_with_redis(None)
def save_report(user_id: str, report: dict) -> None:
    key = _today_key()
    db.hset(key, user_id, json.dumps(report))
    db.expire(key, TTL_REPORT)


# ============ BUILD AUTH ============

@_with_redis(set())
def get_build_authorized() -> set:
    members = db.smembers(KEY_BUILD_AUTH)
    return {m.decode() for m in members} if members else set()


@_with_redis(None)
def add_build_authorized(user_id: str) -> None:
    db.sadd(KEY_BUILD_AUTH, user_id)


@_with_redis(None)
def remove_build_authorized(user_id: str) -> None:
    db.srem(KEY_BUILD_AUTH, user_id)


# ============ BUILD RECORDS ============

@_with_redis(0)
def next_build_id() -> int:
    return db.incr(KEY_BUILD_COUNTER)


@_with_redis(None)
def save_build_record(build_id: int, record: dict) -> None:
    key = f"{KEY_BUILD_PREFIX}:{build_id}"
    db.set(key, json.dumps(record, separators=(",", ":")), ex=TTL_BUILD_RECORD)


@_with_redis(None)
def get_build_record(build_id: int) -> dict | None:
    key = f"{KEY_BUILD_PREFIX}:{build_id}"
    data = db.get(key)
    return json.loads(data) if data else None


@_with_redis([])
def get_recent_builds(count: int = 10) -> list:
    counter = db.get(KEY_BUILD_COUNTER)
    if not counter:
        return []
    latest = int(counter)
    builds = []
    for i in range(latest, max(0, latest - count), -1):
        record = get_build_record(i)
        if record:
            record["id"] = i
            builds.append(record)
    return builds
