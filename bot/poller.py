"""Polling loop + command router."""

import logging
import time

from bot.config import GROUP_CHAT_ID
from bot.telegram import get_updates
from bot.commands.report import handle_report
from bot.commands.member import handle_follow, handle_unfollow, handle_all
from bot.commands.admin import handle_debug, handle_build_auth, handle_build_unauth, handle_help
from bot.commands.build import (
    handle_build, handle_cancel, handle_queue, handle_status,
    handle_log, handle_build_history,
)
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

    return {
        "text": message.get("text", ""),
        "chat_id": chat_id,
        "thread_id": message.get("message_thread_id"),
        "message_id": message.get("message_id"),
        "user_id": user_id,
        "first_name": user.get("first_name", ""),
        "username": user.get("username", ""),
    }


def _dispatch_command(cmd: str, ctx: dict, build_queue: BuildQueue) -> bool:
    """Dispatch command. Trả về True nếu có handler."""
    chat_id = ctx["chat_id"]
    thread_id = ctx["thread_id"]
    text = ctx["text"]
    user_id = ctx["user_id"]
    first_name = ctx["first_name"]
    username = ctx["username"]
    message_id = ctx["message_id"]

    handlers = {
        "/help":          lambda: handle_help(chat_id, thread_id),
        "/debug":         lambda: handle_debug(chat_id, thread_id, user_id),
        "/follow":        lambda: handle_follow(chat_id, thread_id, user_id, first_name, username),
        "/unfollow":      lambda: handle_unfollow(chat_id, thread_id, user_id, first_name),
        "/all":           lambda: handle_all(chat_id, thread_id, message_id, text),
        "/build":         lambda: handle_build(chat_id, thread_id, message_id, text, user_id, first_name, build_queue),
        "/cancel":        lambda: handle_cancel(chat_id, thread_id, text, user_id, build_queue),
        "/queue":         lambda: handle_queue(chat_id, thread_id, build_queue),
        "/status":        lambda: handle_status(chat_id, thread_id, build_queue),
        "/log":           lambda: handle_log(chat_id, thread_id, text),
        "/build_history": lambda: handle_build_history(chat_id, thread_id),
        "/build_auth":    lambda: handle_build_auth(chat_id, thread_id, user_id, text),
        "/build_unauth":  lambda: handle_build_unauth(chat_id, thread_id, user_id, text),
    }

    handler = handlers.get(cmd)
    if handler:
        handler()
        return True
    return False


def handle_update(update: dict, build_queue: BuildQueue) -> None:
    ctx = _extract_message(update)
    if not ctx:
        return

    # Report topic → handle riêng
    if handle_report(ctx["chat_id"], ctx["message_id"], ctx["thread_id"],
                     ctx["text"], ctx["user_id"], ctx["first_name"]):
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
