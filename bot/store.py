import json
import redis
from datetime import datetime

from bot.config import KV_REDIS_URL, KV_KEY, REPORT_KEY_PREFIX, VN_TZ
from bot.config import BUILD_AUTH_KEY, BUILD_COUNTER_KEY, BUILD_PREFIX

try:
    db = redis.from_url(KV_REDIS_URL, socket_timeout=5) if KV_REDIS_URL else None
except Exception:
    db = None


# --- Members ---

def kv_get() -> dict:
    if not db:
        return {}
    try:
        data = db.get(KV_KEY)
        return json.loads(data) if data else {}
    except redis.RedisError:
        return {}


def kv_set(members: dict) -> None:
    if not db:
        return
    try:
        db.set(KV_KEY, json.dumps(members))
    except redis.RedisError:
        pass


# --- Reports (Redis Hash - atomic, no race condition) ---

def get_today_reports() -> dict:
    if not db:
        return {}
    try:
        today = datetime.now(VN_TZ).strftime("%Y-%m-%d")
        key = f"{REPORT_KEY_PREFIX}:{today}"
        data = db.hgetall(key)
        return {k.decode(): json.loads(v) for k, v in data.items()} if data else {}
    except redis.RedisError:
        return {}


def save_report(user_id: str, report: dict) -> None:
    if not db:
        return
    try:
        today = datetime.now(VN_TZ).strftime("%Y-%m-%d")
        key = f"{REPORT_KEY_PREFIX}:{today}"
        db.hset(key, user_id, json.dumps(report))
        db.expire(key, 172800)  # 2-day TTL
    except redis.RedisError:
        pass


# --- Build Auth ---

def get_build_authorized() -> set:
    if not db:
        return set()
    try:
        members = db.smembers(BUILD_AUTH_KEY)
        return {m.decode() for m in members} if members else set()
    except redis.RedisError:
        return set()


def add_build_authorized(user_id: str) -> None:
    if not db:
        return
    try:
        db.sadd(BUILD_AUTH_KEY, user_id)
    except redis.RedisError:
        pass


def remove_build_authorized(user_id: str) -> None:
    if not db:
        return
    try:
        db.srem(BUILD_AUTH_KEY, user_id)
    except redis.RedisError:
        pass


# --- Build Records ---

def next_build_id() -> int:
    if not db:
        return 0
    try:
        return db.incr(BUILD_COUNTER_KEY)
    except redis.RedisError:
        return 0


def save_build_record(build_id: int, record: dict) -> None:
    if not db:
        return
    try:
        key = f"{BUILD_PREFIX}:{build_id}"
        db.set(key, json.dumps(record, separators=(",", ":")), ex=259200)  # 3-day TTL, compact JSON
    except redis.RedisError:
        pass


def get_build_record(build_id: int) -> dict | None:
    if not db:
        return None
    try:
        key = f"{BUILD_PREFIX}:{build_id}"
        data = db.get(key)
        return json.loads(data) if data else None
    except redis.RedisError:
        return None


def get_recent_builds(count: int = 10) -> list:
    """Get recent build records by scanning build:* keys."""
    if not db:
        return []
    try:
        counter = db.get(BUILD_COUNTER_KEY)
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
    except redis.RedisError:
        return []
