import json
import redis
from datetime import datetime

from bot.config import KV_REDIS_URL, KV_KEY, REPORT_KEY_PREFIX, VN_TZ

db = redis.from_url(KV_REDIS_URL) if KV_REDIS_URL else None


def kv_get() -> dict:
    if not db:
        return {}
    data = db.get(KV_KEY)
    return json.loads(data) if data else {}


def kv_set(members: dict) -> None:
    if db:
        db.set(KV_KEY, json.dumps(members))


def get_today_reports() -> dict:
    if not db:
        return {}
    today = datetime.now(VN_TZ).strftime("%Y-%m-%d")
    key = f"{REPORT_KEY_PREFIX}:{today}"
    data = db.get(key)
    return json.loads(data) if data else {}


def save_report(user_id: str, report: dict) -> None:
    if not db:
        return
    today = datetime.now(VN_TZ).strftime("%Y-%m-%d")
    key = f"{REPORT_KEY_PREFIX}:{today}"
    reports = get_today_reports()
    reports[user_id] = report
    db.set(key, json.dumps(reports), ex=172800)  # 2-day TTL
