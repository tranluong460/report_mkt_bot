"""Member commands: /follow, /unfollow, /all."""

import re
from html import escape

from bot.store import kv_get, kv_set
from bot.telegram import send_telegram_message, delete_message
from bot import messages


def handle_follow(chat_id, thread_id, user_id, first_name, username):
    members = kv_get()
    members[user_id] = {"first_name": first_name, "username": username}
    kv_set(members)
    send_telegram_message(chat_id, messages.follow_success(first_name),
                          thread_id, parse_mode="HTML")


def handle_unfollow(chat_id, thread_id, user_id, first_name):
    members = kv_get()
    if user_id in members:
        del members[user_id]
        kv_set(members)
    send_telegram_message(chat_id, messages.unfollow_success(first_name),
                          thread_id, parse_mode="HTML")


def handle_all(chat_id, thread_id, message_id, text):
    content = re.sub(r"^/all(@\S+)?\s*", "", text.strip())
    members = kv_get()

    if not members:
        send_telegram_message(chat_id, messages.no_members(), thread_id)
        return

    mentions = "".join(
        f'<a href="tg://user?id={uid}">\u200b</a>' for uid in members
    )
    safe_content = escape(content) if content else ""
    msg = f"{safe_content}\n{mentions}" if safe_content else mentions

    delete_message(chat_id, message_id)
    send_telegram_message(chat_id, msg, thread_id, parse_mode="HTML")
