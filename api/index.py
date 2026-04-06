import os
import json
import httpx
import redis
from flask import Flask, jsonify, request
from datetime import datetime, timezone, timedelta

app = Flask(__name__)

BOT_TOKEN = os.environ.get("BOT_TOKEN")
GROUP_CHAT_ID = os.environ.get("GROUP_CHAT_ID")
TOPIC_ID = os.environ.get("TOPIC_ID")

TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}"

KV_REDIS_URL = os.environ.get("KV_REDIS_URL")
db = redis.from_url(KV_REDIS_URL) if KV_REDIS_URL else None

VN_TZ = timezone(timedelta(hours=7))
KV_KEY = "members"


# --- Redis helpers ---

def kv_get():
    if not db:
        return {}
    data = db.get(KV_KEY)
    if data:
        return json.loads(data)
    return {}


def kv_set(members):
    if db:
        db.set(KV_KEY, json.dumps(members))


# --- Telegram helpers ---

def send_telegram_message(chat_id, text, thread_id=None):
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "Markdown",
    }
    if thread_id:
        payload["message_thread_id"] = thread_id

    response = httpx.post(f"{TELEGRAM_API}/sendMessage", json=payload)
    return response.json()


def get_report_message():
    today = datetime.now(VN_TZ).strftime("%d/%m/%Y")
    return (
        f"*\U0001F4CB Nhắc báo cáo ngày {today}*\n\n"
        "Mọi người gửi báo cáo công việc hôm nay vào topic này nhé!"
    )


# --- Routes ---

@app.route("/api/index", methods=["GET"])
def cron_handler():
    auth = request.headers.get("Authorization")
    cron_secret = os.environ.get("CRON_SECRET")

    if cron_secret and auth != f"Bearer {cron_secret}":
        return jsonify({"error": "Unauthorized"}), 401

    result = send_telegram_message(
        int(GROUP_CHAT_ID), get_report_message(), int(TOPIC_ID)
    )
    return jsonify(result)


@app.route("/api/index", methods=["POST"])
def webhook_handler():
    data = request.get_json()
    print("WEBHOOK DATA:", json.dumps(data, ensure_ascii=False))
    message = data.get("message", {})
    text = message.get("text", "")
    chat_id = message.get("chat", {}).get("id")
    thread_id = message.get("message_thread_id")
    user = message.get("from", {})
    user_id = str(user.get("id", ""))
    first_name = user.get("first_name", "")
    username = user.get("username", "")

    # /follow - đăng ký nhận tag
    if text.strip() == "/follow":
        members = kv_get()
        members[user_id] = {"first_name": first_name, "username": username}
        kv_set(members)
        send_telegram_message(
            chat_id,
            f"*{first_name}* đã đăng ký nhận thông báo!",
            thread_id,
        )
        return jsonify({"ok": True})

    # /unfollow - hủy đăng ký
    if text.strip() == "/unfollow":
        members = kv_get()
        if user_id in members:
            del members[user_id]
            kv_set(members)
        send_telegram_message(
            chat_id,
            f"*{first_name}* đã hủy đăng ký thông báo.",
            thread_id,
        )
        return jsonify({"ok": True})

    # /all - tag tất cả người đã follow
    if text.strip() in ("/all", "/all@report_mkt_bot"):
        members = kv_get()
        if not members:
            send_telegram_message(
                chat_id,
                "Chưa có ai đăng ký. Dùng /follow để đăng ký nhận tag.",
                thread_id,
            )
        else:
            mentions = []
            for uid, info in members.items():
                if info.get("username"):
                    mentions.append(f"@{info['username']}")
                else:
                    mentions.append(info.get("first_name", uid))
            send_telegram_message(
                chat_id,
                f"\U0001F4E2 {' '.join(mentions)}",
                thread_id,
            )
        return jsonify({"ok": True})

    return jsonify({"ok": True})
