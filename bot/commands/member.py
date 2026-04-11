"""Member commands: /follow, /unfollow, /all."""

import re
from html import escape

from bot.store import get_members, add_member, remove_member
from bot.telegram import send_telegram_message, delete_message
from bot import messages


def handle_follow(chat_id, thread_id, user_id, first_name, username):
    add_member(user_id, first_name, username)
    send_telegram_message(chat_id, messages.follow_success(first_name),
                          thread_id, parse_mode="HTML")


def handle_unfollow(chat_id, thread_id, user_id, first_name):
    remove_member(user_id)
    send_telegram_message(chat_id, messages.unfollow_success(first_name),
                          thread_id, parse_mode="HTML")


def handle_all(chat_id, thread_id, message_id, text):
    content = re.sub(r"^/all(@\S+)?\s*", "", text.strip())
    members = get_members()

    if not members:
        send_telegram_message(chat_id, messages.NO_MEMBERS, thread_id)
        return

    mentions = "".join(
        f'<a href="tg://user?id={uid}">\u200b</a>' for uid in members
    )
    safe_content = escape(content) if content else ""
    msg = f"{safe_content}\n{mentions}" if safe_content else mentions

    delete_message(chat_id, message_id)
    send_telegram_message(chat_id, msg, thread_id, parse_mode="HTML")
