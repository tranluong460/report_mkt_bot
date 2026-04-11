"""Redis storage - members, reports, build records."""

import json
import logging
from datetime import datetime
from functools import wraps

import redis

from bot.config import KV_REDIS_URL, VN_TZ
from bot.constants import (
    KEY_MEMBERS, KEY_REPORT_PREFIX, KEY_BUILD_AUTH, KEY_BUILD_COUNTER, KEY_BUILDS_RECENT,
    KEY_BUILD_ACTIVE,
    TTL_REPORT, TTL_BUILDS_RECENT, MAX_RECENT_BUILDS, REDIS_TIMEOUT,
    DATE_FORMAT_KEY,
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


def _today_report_key() -> str:
    today = datetime.now(VN_TZ).strftime(DATE_FORMAT_KEY)
    return f"{KEY_REPORT_PREFIX}:{today}"


# ============ MEMBERS (Hash) ============

@_with_redis({})
def get_members() -> dict:
    """Trả về dict {user_id: {first_name, username}}."""
    data = db.hgetall(KEY_MEMBERS)
    return {k.decode(): json.loads(v) for k, v in data.items()} if data else {}


@_with_redis(None)
def add_member(user_id: str, first_name: str, username: str) -> None:
    db.hset(KEY_MEMBERS, user_id, json.dumps({"first_name": first_name, "username": username}))


@_with_redis(None)
def remove_member(user_id: str) -> None:
    db.hdel(KEY_MEMBERS, user_id)


# ============ REPORTS (Hash - atomic) ============

@_with_redis({})
def get_today_reports() -> dict:
    data = db.hgetall(_today_report_key())
    return {k.decode(): json.loads(v) for k, v in data.items()} if data else {}


@_with_redis(None)
def save_report(user_id: str, report: dict) -> None:
    key = _today_report_key()
    db.hset(key, user_id, json.dumps(report))
    db.expire(key, TTL_REPORT)


# ============ BUILD AUTH (Set) ============

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


# ============ BUILD RECORDS (List) ============

@_with_redis(0)
def next_build_id() -> int:
    return db.incr(KEY_BUILD_COUNTER)


@_with_redis(None)
def save_build_record(record: dict) -> None:
    """Push build vào đầu list, giữ tối đa MAX_RECENT_BUILDS."""
    db.lpush(KEY_BUILDS_RECENT, json.dumps(record, ensure_ascii=False))
    db.ltrim(KEY_BUILDS_RECENT, 0, MAX_RECENT_BUILDS - 1)
    db.expire(KEY_BUILDS_RECENT, TTL_BUILDS_RECENT)


@_with_redis([])
def get_recent_builds(count: int = 10) -> list:
    """Lấy N builds gần nhất từ list."""
    data = db.lrange(KEY_BUILDS_RECENT, 0, count - 1)
    return [json.loads(item) for item in data] if data else []


# ============ ACTIVE BUILDS (để cleanup orphan messages khi restart) ============

@_with_redis(None)
def register_active_build(build_id: int, info: dict) -> None:
    """Lưu thông tin build đang active (pending hoặc running).
    info gồm: chat_id, build_msg_id, log_msg_id, log_thread_id, project, branch."""
    db.hset(KEY_BUILD_ACTIVE, str(build_id), json.dumps(info))


@_with_redis(None)
def unregister_active_build(build_id: int) -> None:
    """Xoá build khỏi active (khi đã hoàn thành)."""
    db.hdel(KEY_BUILD_ACTIVE, str(build_id))


@_with_redis({})
def get_all_active_builds() -> dict:
    """Lấy tất cả active builds. Dùng khi startup để cleanup."""
    data = db.hgetall(KEY_BUILD_ACTIVE)
    return {k.decode(): json.loads(v) for k, v in data.items()} if data else {}


@_with_redis(None)
def clear_active_builds() -> None:
    """Xoá toàn bộ active builds. Dùng sau khi cleanup startup."""
    db.delete(KEY_BUILD_ACTIVE)
