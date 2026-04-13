"""Admin commands: /debug, /build_auth, /build_unauth, /help, /health."""

import time
from datetime import datetime
from functools import wraps

from bot.config import TOPIC_ID, BUILD_TOPIC_ID, LOG_TOPIC_ID, ADMIN_USER_ID, VN_TZ
from bot.constants import DATE_FORMAT_KEY
from bot.core.store import (
    db, get_today_reports, get_members,
    has_topic_acl, get_topic_acl, add_topic_acl, remove_topic_acl,
    enable_topic_acl, disable_topic_acl, get_all_topic_acls,
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
    members = get_members()
    topic_acl_info = get_all_topic_acls()

    send_html(chat_id, messages.debug_info(
        redis_ok=redis_ok,
        topic_id=TOPIC_ID,
        build_topic_id=BUILD_TOPIC_ID,
        log_topic_id=LOG_TOPIC_ID,
        thread_id=thread_id,
        today=today,
        report_count=len(reports),
        reporters=reporters,
        members_count=len(members),
        uptime_str=_uptime_str(),
        topic_acl_info=topic_acl_info,
    ), thread_id)


# ============ /members ============

@_require_admin
def handle_members(chat_id, thread_id, user_id):
    members = get_members()
    if not members:
        send_html(chat_id, messages.NO_MEMBERS, thread_id)
        return
    send_html(chat_id, messages.members_list(members), thread_id)


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


# ============ TOPIC ACL ============

def _require_log_topic(handler):
    """Decorator: chỉ cho phép gọi trong LOG_TOPIC_ID."""
    @wraps(handler)
    def wrapper(chat_id, thread_id, user_id, *args, **kwargs):
        if not thread_id or str(thread_id) != str(LOG_TOPIC_ID):
            send_html(chat_id, messages.TOPIC_ACL_NOT_IN_LOG, thread_id)
            return
        return handler(chat_id, thread_id, user_id, *args, **kwargs)
    return wrapper


@_require_admin
@_require_log_topic
def handle_topic_auth(chat_id, thread_id, user_id, text):
    parts = text.strip().split()
    if len(parts) < 3 or not parts[2].isdigit():
        send_html(chat_id, messages.TOPIC_AUTH_SYNTAX, thread_id)
        return

    topic_id = parts[1]
    target_id = parts[2]
    add_topic_acl(topic_id, target_id)
    send_html(chat_id, messages.topic_auth_success(topic_id, target_id), thread_id)


@_require_admin
@_require_log_topic
def handle_topic_unauth(chat_id, thread_id, user_id, text):
    parts = text.strip().split()
    if len(parts) < 3 or not parts[2].isdigit():
        send_html(chat_id, messages.TOPIC_UNAUTH_SYNTAX, thread_id)
        return

    topic_id = parts[1]
    target_id = parts[2]
    remove_topic_acl(topic_id, target_id)
    send_html(chat_id, messages.topic_unauth_success(topic_id, target_id), thread_id)


@_require_admin
@_require_log_topic
def handle_topic_acl(chat_id, thread_id, user_id, text):
    parts = text.strip().split()
    if len(parts) < 2:
        send_html(chat_id, messages.TOPIC_ACL_SYNTAX, thread_id)
        return

    topic_id = parts[1]
    sub = parts[2].lower() if len(parts) >= 3 else None

    # /topic_acl <topic_id> list → xem danh sách
    if sub == "list":
        if not has_topic_acl(topic_id):
            send_html(chat_id, messages.topic_acl_no_restriction(topic_id), thread_id)
            return
        acl = get_topic_acl(topic_id)
        send_html(chat_id, messages.topic_acl_list(topic_id, acl), thread_id)
        return

    # /topic_acl <topic_id> → toggle bật/tắt
    if has_topic_acl(topic_id):
        disable_topic_acl(topic_id)
        send_html(chat_id, messages.topic_acl_disabled(topic_id), thread_id)
    else:
        enable_topic_acl(topic_id)
        send_html(chat_id, messages.topic_acl_enabled(topic_id), thread_id)
