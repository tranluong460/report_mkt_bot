import re
from html import escape

from bot.store import kv_get, kv_set
from bot.telegram import send_telegram_message, delete_message


def handle_follow(chat_id: int, thread_id, user_id: str, first_name: str, username: str) -> None:
    members = kv_get()
    members[user_id] = {"first_name": first_name, "username": username}
    kv_set(members)
    send_telegram_message(
        chat_id,
        f"<b>{escape(first_name)}</b> đã đăng ký nhận thông báo!",
        thread_id,
        parse_mode="HTML",
    )


def handle_unfollow(chat_id: int, thread_id, user_id: str, first_name: str) -> None:
    members = kv_get()
    if user_id in members:
        del members[user_id]
        kv_set(members)
    send_telegram_message(
        chat_id,
        f"<b>{escape(first_name)}</b> đã huỷ đăng ký thông báo.",
        thread_id,
        parse_mode="HTML",
    )


def handle_all(chat_id: int, thread_id, message_id: int, text: str) -> None:
    # Extract content, remove /all or /all@botname
    content = re.sub(r"^/all(@\S+)?\s*", "", text.strip())
    members = kv_get()

    if not members:
        send_telegram_message(
            chat_id,
            "Chưa có ai đăng ký. Dùng /follow để đăng ký nhận tag.",
            thread_id,
        )
        return

    mentions = "".join(
        f'<a href="tg://user?id={uid}">\u200b</a>'
        for uid in members
    )
    safe_content = escape(content) if content else ""
    msg = f"{safe_content}\n{mentions}" if safe_content else mentions

    delete_message(chat_id, message_id)
    send_telegram_message(chat_id, msg, thread_id, parse_mode="HTML")
