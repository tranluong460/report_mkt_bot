import logging
import time

from bot.config import GROUP_CHAT_ID
from bot.telegram import get_updates
from bot.commands.report import handle_report
from bot.commands.member import handle_follow, handle_unfollow, handle_all
from bot.commands.admin import handle_debug, handle_build_auth, handle_build_unauth, handle_help
from bot.commands.build import handle_build, handle_cancel, handle_queue, handle_build_history, handle_log, handle_status
from bot.builder.queue import BuildQueue

logger = logging.getLogger(__name__)


def handle_update(update: dict, build_queue: BuildQueue) -> None:
    """Dispatch a single Telegram update to the appropriate handler."""
    message = update.get("message")
    if not message:
        return

    text = message.get("text", "")
    chat_id = message.get("chat", {}).get("id")
    thread_id = message.get("message_thread_id")
    message_id = message.get("message_id")
    user = message.get("from", {})
    user_id = str(user.get("id", ""))
    first_name = user.get("first_name", "")
    username = user.get("username", "")

    if not chat_id or not user_id:
        return

    # Only process messages from our group
    if str(chat_id) != str(GROUP_CHAT_ID):
        return

    # Try report handler first (report topic messages)
    if handle_report(chat_id, message_id, thread_id, text, user_id, first_name):
        return

    # Command routing
    if not text.strip():
        return

    cmd = text.strip().split()[0].split("@")[0].lower()
    logger.info(f"Command: {cmd} | User: {first_name} | Text: {text.strip()[:50]}")

    if cmd == "/help":
        handle_help(chat_id, thread_id)
    elif cmd == "/debug":
        handle_debug(chat_id, thread_id, user_id)
    elif cmd == "/unfollow":
        handle_unfollow(chat_id, thread_id, user_id, first_name)
    elif cmd == "/follow":
        handle_follow(chat_id, thread_id, user_id, first_name, username)
    elif cmd == "/all":
        handle_all(chat_id, thread_id, message_id, text)
    elif cmd == "/build":
        handle_build(chat_id, thread_id, message_id, text, user_id, first_name, build_queue)
    elif cmd == "/cancel":
        handle_cancel(chat_id, thread_id, text, user_id, build_queue)
    elif cmd == "/queue":
        handle_queue(chat_id, thread_id, build_queue)
    elif cmd == "/build_history":
        handle_build_history(chat_id, thread_id)
    elif cmd == "/log":
        handle_log(chat_id, thread_id, text)
    elif cmd == "/status":
        handle_status(chat_id, thread_id, build_queue)
    elif cmd == "/build_auth":
        handle_build_auth(chat_id, thread_id, user_id, text)
    elif cmd == "/build_unauth":
        handle_build_unauth(chat_id, thread_id, user_id, text)


def run_polling(build_queue: BuildQueue, stop_event=None):
    """Main polling loop. Runs until stop_event is set or KeyboardInterrupt."""
    offset = 0
    backoff = 1

    logger.info("Polling started...")

    while True:
        if stop_event and stop_event.is_set():
            break

        try:
            updates = get_updates(offset=offset, timeout=30)

            if updates:
                backoff = 1  # reset backoff on success
                for update in updates:
                    try:
                        handle_update(update, build_queue)
                    except Exception as e:
                        logger.error(f"Error handling update {update.get('update_id')}: {e}")
                    offset = update["update_id"] + 1
            else:
                backoff = 1  # empty response is normal

        except KeyboardInterrupt:
            break
        except Exception as e:
            logger.error(f"Polling error: {e}")
            time.sleep(min(backoff, 60))
            backoff = min(backoff * 2, 60)

    logger.info("Polling stopped.")
