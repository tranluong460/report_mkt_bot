"""Polling loop + command router."""

import logging
import time
from threading import Timer

from bot.config import GROUP_CHAT_ID, ADMIN_USER_ID
from bot.constants import TTL_TOPIC_ACL_WARNING
from bot.core.store import has_topic_acl, get_topic_acl
from bot.core.telegram import get_updates, answer_callback_query, delete_message, send_html
from bot.commands.report import handle_report
from bot.commands.member import handle_follow, handle_unfollow, handle_all
from bot.commands.admin import (
    handle_debug, handle_help, handle_health,
    handle_topic_auth, handle_topic_unauth, handle_topic_acl,
)
from bot.commands.build import (
    handle_build, handle_cancel, handle_queue, handle_status,
    handle_log, handle_build_history, handle_retry, handle_stats,
    handle_retry_callback, handle_edit,
)
from bot.commands.export import handle_export
from bot.builder.queue import BuildQueue

logger = logging.getLogger("bot.poller")


def _extract_message(update: dict) -> dict | None:
    """Extract + validate message fields. Trả về dict hoặc None nếu invalid."""
    message = update.get("message")
    if not message:
        return None

    chat_id = message.get("chat", {}).get("id")
    user = message.get("from", {})
    user_id = str(user.get("id", ""))

    if not chat_id or not user_id:
        return None
    if str(chat_id) != str(GROUP_CHAT_ID):
        return None

    reply = message.get("reply_to_message")
    return {
        "text": message.get("text", ""),
        "chat_id": chat_id,
        "thread_id": message.get("message_thread_id"),
        "message_id": message.get("message_id"),
        "user_id": user_id,
        "first_name": user.get("first_name", ""),
        "username": user.get("username", ""),
        "reply_to_message_id": reply.get("message_id") if reply else None,
    }


def _check_topic_acl(chat_id: int, thread_id, message_id: int, user_id: str) -> bool:
    """Kiểm tra user có quyền nhắn tin trong topic không.
    Trả về True nếu được phép, False nếu bị chặn (đã xóa tin + gửi cảnh báo).
    """
    if not thread_id:
        return True
    # Admin luôn bypass
    if ADMIN_USER_ID and user_id == str(ADMIN_USER_ID):
        return True
    # Topic chưa thiết lập ACL → mở cho tất cả
    if not has_topic_acl(thread_id):
        return True
    # Kiểm tra user trong whitelist
    acl = get_topic_acl(thread_id)
    if user_id in acl:
        return True

    # Chặn: xóa tin nhắn + gửi cảnh báo tự hủy sau 3s
    from bot import messages
    delete_message(chat_id, message_id)
    result = send_html(chat_id, messages.TOPIC_ACL_DENIED, thread_id)
    warning_id = result.get("result", {}).get("message_id") if result.get("ok") else None
    if warning_id:
        Timer(TTL_TOPIC_ACL_WARNING, delete_message, [chat_id, warning_id]).start()
    return False


def _dispatch_command(cmd: str, ctx: dict, build_queue: BuildQueue) -> bool:
    """Dispatch command. Trả về True nếu có handler."""
    chat_id = ctx["chat_id"]
    thread_id = ctx["thread_id"]
    text = ctx["text"]
    user_id = ctx["user_id"]
    first_name = ctx["first_name"]
    username = ctx["username"]
    message_id = ctx["message_id"]
    reply_to = ctx["reply_to_message_id"]

    handlers = {
        "/help":          lambda: handle_help(chat_id, thread_id),
        "/health":        lambda: handle_health(chat_id, thread_id, build_queue),
        "/debug":         lambda: handle_debug(chat_id, thread_id, user_id),
        "/follow":        lambda: handle_follow(chat_id, thread_id, user_id, first_name, username),
        "/unfollow":      lambda: handle_unfollow(chat_id, thread_id, user_id, first_name),
        "/all":           lambda: handle_all(chat_id, thread_id, message_id, text),
        "/build":         lambda: handle_build(chat_id, thread_id, message_id, text, user_id, first_name, build_queue),
        "/retry":         lambda: handle_retry(chat_id, thread_id, message_id, text, user_id, first_name, build_queue),
        "/cancel":        lambda: handle_cancel(chat_id, thread_id, text, user_id, build_queue),
        "/queue":         lambda: handle_queue(chat_id, thread_id, build_queue),
        "/status":        lambda: handle_status(chat_id, thread_id, build_queue),
        "/log":           lambda: handle_log(chat_id, thread_id, text),
        "/build_history": lambda: handle_build_history(chat_id, thread_id),
        "/stats":         lambda: handle_stats(chat_id, thread_id),
        "/export":        lambda: handle_export(chat_id, thread_id),
        "/edit":          lambda: handle_edit(chat_id, thread_id, message_id, text, reply_to),
        "/topic_auth":    lambda: handle_topic_auth(chat_id, thread_id, user_id, text),
        "/topic_unauth":  lambda: handle_topic_unauth(chat_id, thread_id, user_id, text),
        "/topic_acl":     lambda: handle_topic_acl(chat_id, thread_id, user_id, text),
    }

    handler = handlers.get(cmd)
    if handler:
        handler()
        return True
    return False


def _handle_callback_query(update: dict, build_queue: BuildQueue) -> None:
    """Xử lý click inline button."""
    cb = update.get("callback_query", {})
    cb_id = cb.get("id")
    data = cb.get("data", "")
    message = cb.get("message", {})
    chat_id = message.get("chat", {}).get("id")
    msg_id = message.get("message_id")

    if not cb_id or not chat_id or not msg_id:
        return

    # callback_data format: "cancel:<build_id>"
    if data.startswith("cancel:"):
        try:
            build_id = int(data.split(":", 1)[1])
        except (ValueError, IndexError):
            answer_callback_query(cb_id, "Dữ liệu không hợp lệ")
            return

        if build_queue.cancel(build_id):
            delete_message(chat_id, msg_id)
            answer_callback_query(cb_id, f"Đã huỷ Build #{build_id}")
        else:
            answer_callback_query(cb_id, "Không huỷ được (có thể đang chạy)")
        return

    # callback_data format: "retry:<build_id>"
    if data.startswith("retry:"):
        try:
            build_id = int(data.split(":", 1)[1])
        except (ValueError, IndexError):
            answer_callback_query(cb_id, "Dữ liệu không hợp lệ")
            return

        from_user = cb.get("from", {})
        user_id = from_user.get("id")
        first_name = from_user.get("first_name", "Unknown")

        success, msg = handle_retry_callback(
            chat_id, msg_id, build_id, user_id, first_name, build_queue,
        )
        answer_callback_query(cb_id, msg)
        return

    answer_callback_query(cb_id)


def handle_update(update: dict, build_queue: BuildQueue) -> None:
    # Callback query (inline button)
    if "callback_query" in update:
        _handle_callback_query(update, build_queue)
        return

    ctx = _extract_message(update)
    if not ctx:
        return

    # Topic ACL check - chặn trước khi xử lý bất kỳ thứ gì
    if not _check_topic_acl(ctx["chat_id"], ctx["thread_id"], ctx["message_id"], ctx["user_id"]):
        return

    # Report topic → handle riêng
    if handle_report(ctx["chat_id"], ctx["message_id"], ctx["thread_id"],
                     ctx["text"], ctx["user_id"], ctx["first_name"],
                     ctx["username"]):
        return

    text = ctx["text"].strip()
    if not text:
        return

    # Command: lấy phần đầu, bỏ @botname
    cmd = text.split()[0].split("@")[0].lower()
    _dispatch_command(cmd, ctx, build_queue)


def run_polling(build_queue: BuildQueue, stop_event=None):
    """Vòng lặp getUpdates. Chạy đến khi stop_event được set."""
    offset = 0
    backoff = 1

    logger.info("Polling started")

    while True:
        if stop_event and stop_event.is_set():
            break

        try:
            updates = get_updates(offset=offset, timeout=30)
            for update in updates:
                try:
                    handle_update(update, build_queue)
                except Exception as e:
                    logger.error(f"Error handling update {update.get('update_id')}: {e}")
                offset = update["update_id"] + 1
            backoff = 1

        except KeyboardInterrupt:
            break
        except Exception as e:
            logger.error(f"Polling error: {e}")
            time.sleep(min(backoff, 60))
            backoff = min(backoff * 2, 60)

    logger.info("Polling stopped")
