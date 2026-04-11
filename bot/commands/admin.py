"""Admin commands: /debug, /build_auth, /build_unauth, /help, /health."""

import time
from datetime import datetime
from functools import wraps

from bot.config import TOPIC_ID, BUILD_TOPIC_ID, ADMIN_USER_ID, VN_TZ
from bot.constants import DATE_FORMAT_KEY
from bot.core.store import (
    db, get_today_reports, get_build_authorized,
    add_build_authorized, remove_build_authorized, get_members,
)
from bot.core.telegram import send_html
from bot import messages

_START_TIME = time.time()


def _uptime_str() -> str:
    seconds = int(time.time() - _START_TIME)
    days, rem = divmod(seconds, 86400)
    hours, rem = divmod(rem, 3600)
    minutes, _ = divmod(rem, 60)
    if days:
        return f"{days}d {hours}h {minutes}m"
    if hours:
        return f"{hours}h {minutes}m"
    return f"{minutes}m"


def _require_admin(handler):
    """Decorator: chỉ admin mới gọi được."""
    @wraps(handler)
    def wrapper(chat_id, thread_id, user_id, *args, **kwargs):
        if ADMIN_USER_ID and user_id != str(ADMIN_USER_ID):
            send_html(chat_id, messages.ADMIN_ONLY, thread_id)
            return
        return handler(chat_id, thread_id, user_id, *args, **kwargs)
    return wrapper


# ============ /debug ============

@_require_admin
def handle_debug(chat_id, thread_id, user_id):
    redis_ok = db is not None
    reports = get_today_reports() if redis_ok else {}
    today = datetime.now(VN_TZ).strftime(DATE_FORMAT_KEY)
    reporters = [r.get("name", uid) for uid, r in reports.items()]
    authorized = get_build_authorized()

    send_html(chat_id, messages.debug_info(
        redis_ok=redis_ok,
        topic_id=TOPIC_ID,
        build_topic_id=BUILD_TOPIC_ID,
        thread_id=thread_id,
        today=today,
        report_count=len(reports),
        reporters=reporters,
        auth_count=len(authorized),
    ), thread_id)


# ============ /build_auth ============

@_require_admin
def handle_build_auth(chat_id, thread_id, user_id, text):
    parts = text.strip().split()
    if len(parts) < 2:
        send_html(chat_id, messages.BUILD_AUTH_SYNTAX, thread_id)
        return

    target_id = parts[1]
    add_build_authorized(target_id)
    send_html(chat_id, messages.build_auth_success(target_id), thread_id)


# ============ /build_unauth ============

@_require_admin
def handle_build_unauth(chat_id, thread_id, user_id, text):
    parts = text.strip().split()
    if len(parts) < 2:
        send_html(chat_id, messages.BUILD_UNAUTH_SYNTAX, thread_id)
        return

    target_id = parts[1]
    remove_build_authorized(target_id)
    send_html(chat_id, messages.build_unauth_success(target_id), thread_id)


# ============ /help ============

def handle_help(chat_id, thread_id):
    send_html(chat_id, messages.HELP_TEXT, thread_id)


# ============ /health ============

def handle_health(chat_id, thread_id, build_queue):
    redis_ok = False
    if db is not None:
        try:
            db.ping()
            redis_ok = True
        except Exception:
            redis_ok = False

    members_count = len(get_members())
    status = build_queue.get_status()

    send_html(chat_id, messages.health_status(
        redis_ok=redis_ok,
        members_count=members_count,
        running_count=len(status["running"]),
        pending_count=len(status["pending"]),
        uptime_str=_uptime_str(),
    ), thread_id)
