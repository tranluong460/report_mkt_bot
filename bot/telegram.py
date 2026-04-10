import httpx
from datetime import datetime

from bot.config import TELEGRAM_API, VN_TZ

# Persistent client for connection reuse
_client = httpx.Client(timeout=httpx.Timeout(connect=10, read=35, write=10, pool=10))


def react_to_message(chat_id: int, message_id: int, emoji: str) -> None:
    """React to a message with an emoji reaction."""
    try:
        _client.post(
            f"{TELEGRAM_API}/setMessageReaction",
            json={
                "chat_id": chat_id,
                "message_id": message_id,
                "reaction": [{"type": "emoji", "emoji": emoji}],
            },
        )
    except httpx.HTTPError:
        pass


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
    if thread_id is not None:
        payload["message_thread_id"] = thread_id

    try:
        response = _client.post(f"{TELEGRAM_API}/sendMessage", json=payload)
        return response.json()
    except httpx.HTTPError:
        return {"ok": False}


def edit_message(chat_id: int, message_id: int, text: str, parse_mode: str = "Markdown") -> dict:
    """Edit an existing message."""
    try:
        response = _client.post(
            f"{TELEGRAM_API}/editMessageText",
            json={
                "chat_id": chat_id,
                "message_id": message_id,
                "text": text,
                "parse_mode": parse_mode,
            },
        )
        return response.json()
    except httpx.HTTPError:
        return {"ok": False}


def delete_message(chat_id: int, message_id: int) -> None:
    """Delete a message."""
    try:
        _client.post(
            f"{TELEGRAM_API}/deleteMessage",
            json={"chat_id": chat_id, "message_id": message_id},
        )
    except httpx.HTTPError:
        pass


def get_updates(offset: int = 0, timeout: int = 30) -> list:
    """Long-poll for new updates from Telegram."""
    try:
        response = _client.post(
            f"{TELEGRAM_API}/getUpdates",
            json={
                "offset": offset,
                "timeout": timeout,
                "allowed_updates": ["message"],
            },
        )
        data = response.json()
        return data.get("result", [])
    except httpx.HTTPError:
        return []


def delete_webhook() -> bool:
    """Delete any existing webhook so getUpdates works."""
    try:
        response = _client.post(f"{TELEGRAM_API}/deleteWebhook")
        data = response.json()
        return data.get("ok", False)
    except httpx.HTTPError:
        return False


def send_document(chat_id: int, file_path: str, caption: str = "", thread_id: int | None = None) -> dict:
    """Send a file as a document."""
    try:
        data = {"chat_id": str(chat_id)}
        if caption:
            data["caption"] = caption
        if thread_id is not None:
            data["message_thread_id"] = str(thread_id)

        with open(file_path, "rb") as f:
            response = _client.post(
                f"{TELEGRAM_API}/sendDocument",
                data=data,
                files={"document": f},
            )
        return response.json()
    except (httpx.HTTPError, FileNotFoundError):
        return {"ok": False}


def get_report_message() -> str:
    today = datetime.now(VN_TZ).strftime("%d/%m/%Y")
    return (
        f"*\U0001F4CB Nh\u1eafc b\u00e1o c\u00e1o ng\u00e0y {today}*\n\n"
        "M\u1ecdi ng\u01b0\u1eddi g\u1eedi b\u00e1o c\u00e1o c\u00f4ng vi\u1ec7c h\u00f4m nay v\u00e0o topic n\u00e0y nh\u00e9!"
    )


def escape_markdown(text: str) -> str:
    """Escape Markdown special characters."""
    for ch in ("\\", "_", "*", "[", "]", "(", ")", "~", "`", ">", "#", "+", "-", "=", "|", "{", "}", ".", "!"):
        text = text.replace(ch, f"\\{ch}")
    return text
