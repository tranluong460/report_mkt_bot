import httpx
from datetime import datetime

from bot.config import TELEGRAM_API, VN_TZ


def react_to_message(chat_id: int, message_id: int, emoji: str) -> None:
    """React to a message with an emoji reaction."""
    httpx.post(
        f"{TELEGRAM_API}/setMessageReaction",
        json={
            "chat_id": chat_id,
            "message_id": message_id,
            "reaction": [{"type": "emoji", "emoji": emoji}],
        },
    )


def send_telegram_message(
    chat_id: int,
    text: str,
    thread_id: int | None = None,
    parse_mode: str = "Markdown",
) -> dict:
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": parse_mode,
    }
    if thread_id:
        payload["message_thread_id"] = thread_id

    response = httpx.post(f"{TELEGRAM_API}/sendMessage", json=payload)
    return response.json()


def get_report_message() -> str:
    today = datetime.now(VN_TZ).strftime("%d/%m/%Y")
    return (
        f"*\U0001F4CB Nhắc báo cáo ngày {today}*\n\n"
        "Mọi người gửi báo cáo công việc hôm nay vào topic này nhé!"
    )
