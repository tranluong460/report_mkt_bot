"""Wrapper cho Telegram Bot API - chỉ chứa HTTP calls."""

import json
import logging

import httpx

from bot.config import TELEGRAM_API

logger = logging.getLogger("bot.telegram")

_client = httpx.Client(timeout=httpx.Timeout(connect=10, read=300, write=300, pool=10))


# ============ SEND / EDIT MESSAGE ============

def send_telegram_message(
    chat_id: int,
    text: str,
    thread_id: int | None = None,
    parse_mode: str = "Markdown",
) -> dict:
    payload = {"chat_id": chat_id, "text": text, "parse_mode": parse_mode}
    if thread_id is not None:
        payload["message_thread_id"] = thread_id
    try:
        response = _client.post(f"{TELEGRAM_API}/sendMessage", json=payload)
        return response.json()
    except httpx.HTTPError as e:
        logger.warning(f"sendMessage failed: {e}")
        return {"ok": False}


def edit_message(chat_id: int, message_id: int, text: str, parse_mode: str = "Markdown") -> dict:
    try:
        response = _client.post(
            f"{TELEGRAM_API}/editMessageText",
            json={"chat_id": chat_id, "message_id": message_id, "text": text, "parse_mode": parse_mode},
        )
        return response.json()
    except httpx.HTTPError as e:
        logger.warning(f"editMessageText failed: {e}")
        return {"ok": False}


def edit_message_caption(chat_id: int, message_id: int, caption: str, parse_mode: str = "HTML") -> dict:
    try:
        response = _client.post(
            f"{TELEGRAM_API}/editMessageCaption",
            json={"chat_id": chat_id, "message_id": message_id, "caption": caption, "parse_mode": parse_mode},
        )
        return response.json()
    except httpx.HTTPError as e:
        logger.warning(f"editMessageCaption failed: {e}")
        return {"ok": False}


def delete_message(chat_id: int, message_id: int) -> None:
    try:
        _client.post(
            f"{TELEGRAM_API}/deleteMessage",
            json={"chat_id": chat_id, "message_id": message_id},
        )
    except httpx.HTTPError as e:
        logger.warning(f"deleteMessage failed: {e}")


# ============ REACTION ============

def react_to_message(chat_id: int, message_id: int, emoji: str) -> None:
    try:
        _client.post(
            f"{TELEGRAM_API}/setMessageReaction",
            json={
                "chat_id": chat_id,
                "message_id": message_id,
                "reaction": [{"type": "emoji", "emoji": emoji}],
            },
        )
    except httpx.HTTPError as e:
        logger.warning(f"setMessageReaction failed: {e}")


# ============ FILE / MEDIA ============

def send_document(
    chat_id: int,
    file_path: str,
    caption: str = "",
    thread_id: int | None = None,
    parse_mode: str | None = None,
) -> dict:
    try:
        data = {"chat_id": str(chat_id)}
        if caption:
            data["caption"] = caption
        if parse_mode:
            data["parse_mode"] = parse_mode
        if thread_id is not None:
            data["message_thread_id"] = str(thread_id)

        with open(file_path, "rb") as f:
            response = _client.post(
                f"{TELEGRAM_API}/sendDocument",
                data=data,
                files={"document": f},
            )
        return response.json()
    except (httpx.HTTPError, FileNotFoundError) as e:
        logger.warning(f"sendDocument failed: {e}")
        return {"ok": False}


def edit_message_media(
    chat_id: int,
    message_id: int,
    file_path: str,
    caption: str = "",
    parse_mode: str = "HTML",
) -> dict:
    """Thay file + caption của document message."""
    try:
        media = json.dumps({
            "type": "document",
            "media": "attach://document",
            "caption": caption,
            "parse_mode": parse_mode,
        })
        data = {
            "chat_id": str(chat_id),
            "message_id": str(message_id),
            "media": media,
        }
        with open(file_path, "rb") as f:
            response = _client.post(
                f"{TELEGRAM_API}/editMessageMedia",
                data=data,
                files={"document": f},
            )
        result = response.json()
        if not result.get("ok"):
            logger.warning(f"editMessageMedia failed: {result}")
        return result
    except (httpx.HTTPError, FileNotFoundError) as e:
        logger.warning(f"editMessageMedia error: {e}")
        return {"ok": False}


# ============ WEBHOOK ============

def get_updates(offset: int = 0, timeout: int = 30) -> list:
    try:
        response = _client.post(
            f"{TELEGRAM_API}/getUpdates",
            json={"offset": offset, "timeout": timeout, "allowed_updates": ["message"]},
        )
        return response.json().get("result", [])
    except httpx.HTTPError as e:
        logger.warning(f"getUpdates failed: {e}")
        return []


def delete_webhook() -> bool:
    try:
        response = _client.post(f"{TELEGRAM_API}/deleteWebhook")
        return response.json().get("ok", False)
    except httpx.HTTPError:
        return False
