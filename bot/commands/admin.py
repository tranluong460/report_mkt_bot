"""Admin commands: /debug, /build_auth, /build_unauth, /help."""

from datetime import datetime
from functools import wraps

from bot.config import TOPIC_ID, BUILD_TOPIC_ID, ADMIN_USER_ID, VN_TZ
from bot.store import db, get_today_reports, get_build_authorized, add_build_authorized, remove_build_authorized
from bot.telegram import send_telegram_message
from bot import messages


def _require_admin(handler):
    """Decorator: chỉ admin mới gọi được."""
    @wraps(handler)
    def wrapper(chat_id, thread_id, user_id, *args, **kwargs):
        if ADMIN_USER_ID and user_id != str(ADMIN_USER_ID):
            send_telegram_message(chat_id, "Chỉ admin mới dùng được lệnh này.", thread_id)
            return
        return handler(chat_id, thread_id, user_id, *args, **kwargs)
    return wrapper


# ============ /debug ============

@_require_admin
def handle_debug(chat_id, thread_id, user_id):
    redis_ok = db is not None
    reports = get_today_reports() if redis_ok else {}
    today = datetime.now(VN_TZ).strftime("%Y-%m-%d")
    reporters = [r.get("name", uid) for uid, r in reports.items()]
    authorized = get_build_authorized()

    msg = messages.debug_info(
        redis_ok=redis_ok,
        topic_id=TOPIC_ID,
        build_topic_id=BUILD_TOPIC_ID,
        thread_id=thread_id,
        today=today,
        report_count=len(reports),
        reporters=reporters,
        auth_count=len(authorized),
    )
    send_telegram_message(chat_id, msg, thread_id, parse_mode="HTML")


# ============ /build_auth ============

@_require_admin
def handle_build_auth(chat_id, thread_id, user_id, text):
    parts = text.strip().split()
    if len(parts) < 2:
        send_telegram_message(
            chat_id, "<b>Cú pháp:</b> <code>/build_auth &lt;user_id&gt;</code>",
            thread_id, parse_mode="HTML",
        )
        return

    target_id = parts[1]
    add_build_authorized(target_id)
    send_telegram_message(
        chat_id, f"User <code>{target_id}</code> đã được cấp quyền build.",
        thread_id, parse_mode="HTML",
    )


# ============ /build_unauth ============

@_require_admin
def handle_build_unauth(chat_id, thread_id, user_id, text):
    parts = text.strip().split()
    if len(parts) < 2:
        send_telegram_message(
            chat_id, "<b>Cú pháp:</b> <code>/build_unauth &lt;user_id&gt;</code>",
            thread_id, parse_mode="HTML",
        )
        return

    target_id = parts[1]
    remove_build_authorized(target_id)
    send_telegram_message(
        chat_id, f"User <code>{target_id}</code> đã bị xoá quyền build.",
        thread_id, parse_mode="HTML",
    )


# ============ /help ============

def handle_help(chat_id, thread_id):
    send_telegram_message(chat_id, messages.HELP_TEXT, thread_id, parse_mode="HTML")
