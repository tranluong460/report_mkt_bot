"""Redis storage - members, reports, build records."""

import json
import logging
from functools import wraps

import redis

from bot.config import KV_REDIS_URL
from bot.constants import (
    KEY_MEMBERS, KEY_BUILD_COUNTER, KEY_BUILDS_RECENT,
    KEY_BUILD_ACTIVE, KEY_TOPIC_ACL_PREFIX,
    KEY_TASK_PREFIX_MAP, KEY_USER_LINK_MAP,
    TTL_BUILDS_RECENT, MAX_RECENT_BUILDS, REDIS_TIMEOUT,
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


# ============ TOPIC ACL (Set per topic) ============

def _topic_acl_key(thread_id) -> str:
    return f"{KEY_TOPIC_ACL_PREFIX}:{thread_id}"


@_with_redis(False)
def has_topic_acl(thread_id) -> bool:
    """Kiểm tra topic có thiết lập ACL không. True = có whitelist."""
    return db.exists(_topic_acl_key(thread_id)) == 1


@_with_redis(set())
def get_topic_acl(thread_id) -> set:
    """Trả về set user_id được phép nhắn trong topic (không bao gồm marker)."""
    members = db.smembers(_topic_acl_key(thread_id))
    if not members:
        return set()
    return {m.decode() for m in members if m.decode() != "__acl_enabled__"}


@_with_redis(None)
def add_topic_acl(thread_id, user_id: str) -> None:
    """Thêm user vào whitelist topic."""
    db.sadd(_topic_acl_key(thread_id), user_id)


@_with_redis(None)
def remove_topic_acl(thread_id, user_id: str) -> None:
    """Xoá user khỏi whitelist topic."""
    db.srem(_topic_acl_key(thread_id), user_id)


@_with_redis(None)
def enable_topic_acl(thread_id) -> None:
    """Bật ACL cho topic. Dùng marker __acl_enabled__ để đảm bảo key tồn tại."""
    db.sadd(_topic_acl_key(thread_id), "__acl_enabled__")


@_with_redis(None)
def disable_topic_acl(thread_id) -> None:
    """Tắt ACL cho topic (xóa key → topic mở cho tất cả)."""
    db.delete(_topic_acl_key(thread_id))


# ============ TASK PREFIX → BUILD FOLDER (Hash) ============

@_with_redis({})
def get_task_prefix_map() -> dict:
    """{PREFIX: folder}, ví dụ {'MKT-CARE': 'mkt-care-2025'}."""
    data = db.hgetall(KEY_TASK_PREFIX_MAP)
    return {k.decode(): v.decode() for k, v in data.items()} if data else {}


@_with_redis(None)
def set_task_prefix(prefix: str, folder: str) -> None:
    db.hset(KEY_TASK_PREFIX_MAP, prefix.upper(), folder)


@_with_redis(None)
def del_task_prefix(prefix: str) -> None:
    db.hdel(KEY_TASK_PREFIX_MAP, prefix.upper())


def folder_to_prefix(folder: str) -> str | None:
    """Reverse lookup: folder → PREFIX. None nếu chưa map."""
    for prefix, fld in get_task_prefix_map().items():
        if fld == folder:
            return prefix
    return None


# ============ USER LINK: vitech assignee_id → telegram user_id (Hash) ============

@_with_redis({})
def get_user_link_map() -> dict:
    """{vitech_assignee_id: telegram_user_id}."""
    data = db.hgetall(KEY_USER_LINK_MAP)
    return {k.decode(): v.decode() for k, v in data.items()} if data else {}


@_with_redis(None)
def set_user_link(assignee_id: str, tg_user_id: str) -> None:
    db.hset(KEY_USER_LINK_MAP, assignee_id, tg_user_id)


@_with_redis(None)
def del_user_link(assignee_id: str) -> None:
    db.hdel(KEY_USER_LINK_MAP, assignee_id)


@_with_redis({})
def get_all_topic_acls() -> dict:
    """Trả về dict {topic_id: set(user_ids)} cho tất cả topic có ACL."""
    result = {}
    cursor = 0
    pattern = f"{KEY_TOPIC_ACL_PREFIX}:*"
    while True:
        cursor, keys = db.scan(cursor, match=pattern, count=100)
        for key in keys:
            topic_id = key.decode().split(":", 2)[2]
            members = db.smembers(key)
            user_ids = {m.decode() for m in members if m.decode() != "__acl_enabled__"} if members else set()
            result[topic_id] = user_ids
        if cursor == 0:
            break
    return result
