"""Vitech Task API client.

- Login bằng email/password (env), cache accessToken in-memory.
- Tự re-login khi gặp 401.
- fetch_all_tasks(): paginate qua toàn bộ task (excludeSubTasks=true).
"""

from __future__ import annotations

import logging
import re
import threading
from datetime import datetime, timedelta

import httpx

from bot.config import VITECH_API_URL, VITECH_API_EMAIL, VITECH_API_PASSWORD, VN_TZ

logger = logging.getLogger("bot.vitech")

_LOCK = threading.Lock()
_TOKEN: str | None = None
_HTTP_TIMEOUT = 15.0
_PAGE_LIMIT = 100


def _login() -> str:
    """Gọi POST /auth/login để lấy accessToken. Không catch exception."""
    url = f"{VITECH_API_URL}/api/v1/auth/login"
    resp = httpx.post(
        url,
        json={"email": VITECH_API_EMAIL, "password": VITECH_API_PASSWORD},
        timeout=_HTTP_TIMEOUT,
    )
    resp.raise_for_status()
    data = resp.json()
    token = data.get("data", {}).get("accessToken")
    if not token:
        raise RuntimeError(f"Login response missing accessToken: {data}")
    logger.info("Vitech login OK")
    return token


def get_token(force_refresh: bool = False) -> str:
    """Trả về access token (cache in-memory). Tự login nếu chưa có/hết hạn."""
    global _TOKEN
    with _LOCK:
        if force_refresh or not _TOKEN:
            _TOKEN = _login()
        return _TOKEN


def _request(method: str, path: str, *, params=None, json=None) -> dict:
    """HTTP request với Bearer token. Tự re-login 1 lần khi 401."""
    url = f"{VITECH_API_URL}{path}"
    for attempt in (1, 2):
        token = get_token(force_refresh=(attempt == 2))
        resp = httpx.request(
            method, url,
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/json",
                "Referer": "https://dev.vitechgroup.vn/",
                "Origin": "https://dev.vitechgroup.vn",
            },
            params=params, json=json, timeout=_HTTP_TIMEOUT,
        )
        if resp.status_code == 401 and attempt == 1:
            logger.info("Vitech 401, refreshing token...")
            continue
        resp.raise_for_status()
        return resp.json()
    raise RuntimeError("Unreachable")


# ============ Tasks ============

def fetch_all_tasks() -> list[dict]:
    """Paginate toàn bộ tasks (excludeSubTasks=true)."""
    all_tasks: list[dict] = []
    page = 1
    while True:
        data = _request("GET", "/api/v1/tasks", params={
            "page": page, "limit": _PAGE_LIMIT, "excludeSubTasks": "true",
        })
        items = data.get("data", []) or []
        all_tasks.extend(items)
        meta = data.get("meta", {})
        total_pages = meta.get("totalPages", 1)
        if page >= total_pages or not items:
            break
        page += 1
    return all_tasks


# ============ Helpers ============

_UTC_RE = re.compile(r"\.\d+Z$")


def parse_utc(ts: str) -> datetime | None:
    """Parse ISO UTC '2026-04-15T06:40:02.671Z' → aware datetime (UTC)."""
    if not ts:
        return None
    try:
        # Normalize Z → +00:00, Python 3.11+ handles fromisoformat with Z directly
        s = ts.replace("Z", "+00:00")
        return datetime.fromisoformat(s)
    except Exception:
        return None


def is_today_vn(ts: str) -> bool:
    """True nếu timestamp UTC thuộc ngày hôm nay theo giờ VN."""
    dt = parse_utc(ts)
    if not dt:
        return False
    today_vn = datetime.now(VN_TZ).date()
    return dt.astimezone(VN_TZ).date() == today_vn


def within_last_minutes(ts: str, minutes: int) -> bool:
    """True nếu timestamp nằm trong [now - minutes, now]."""
    dt = parse_utc(ts)
    if not dt:
        return False
    now_utc = datetime.now(dt.tzinfo)
    return (now_utc - dt) <= timedelta(minutes=minutes) and dt <= now_utc


def task_prefix(code: str) -> str:
    """MKT-FORUM-001 → MKT-FORUM. Bỏ đuôi -NNN."""
    if not code:
        return ""
    return re.sub(r"-\d+$", "", code)


def tasks_updated_today(tasks: list[dict]) -> list[dict]:
    return [t for t in tasks if is_today_vn(t.get("updatedAt"))]


def is_in_current_week_vn(ts: str) -> bool:
    """True nếu timestamp UTC thuộc tuần hiện tại theo giờ VN (T2 → T7)."""
    dt = parse_utc(ts)
    if not dt:
        return False
    today_vn = datetime.now(VN_TZ).date()
    monday = today_vn - timedelta(days=today_vn.weekday())
    saturday = monday + timedelta(days=5)
    d = dt.astimezone(VN_TZ).date()
    return monday <= d <= saturday


def tasks_updated_this_week(tasks: list[dict]) -> list[dict]:
    return [t for t in tasks if is_in_current_week_vn(t.get("updatedAt"))]


def tasks_by_prefix(tasks: list[dict], prefix: str) -> list[dict]:
    """Lọc tasks có code bắt đầu bằng PREFIX-."""
    p = f"{prefix.upper()}-"
    return [t for t in tasks if (t.get("code") or "").upper().startswith(p)]


def fetch_today_tasks_for_folder(folder: str) -> tuple[list[dict] | None, str | None]:
    """Lấy tasks hôm nay cho 1 folder. Trả về (tasks, prefix) hoặc (None, None) nếu chưa map."""
    from bot.core.store import folder_to_prefix
    prefix = folder_to_prefix(folder)
    if not prefix:
        return None, None
    today = tasks_updated_today(fetch_all_tasks())
    return tasks_by_prefix(today, prefix), prefix
