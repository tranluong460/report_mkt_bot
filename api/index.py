import os
import httpx
from datetime import datetime, timezone, timedelta

BOT_TOKEN = os.environ.get("BOT_TOKEN")
GROUP_CHAT_ID = os.environ.get("GROUP_CHAT_ID")
TOPIC_ID = os.environ.get("TOPIC_ID")

TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}"

VN_TZ = timezone(timedelta(hours=7))


def get_message():
    today = datetime.now(VN_TZ).strftime("%d/%m/%Y")
    return (
        f"*\U0001F4CB Nhắc báo cáo ngày {today}*\n\n"
        "Mọi người gửi báo cáo công việc hôm nay vào topic này nhé!"
    )


def send_message():
    response = httpx.post(
        f"{TELEGRAM_API}/sendMessage",
        json={
            "chat_id": int(GROUP_CHAT_ID),
            "message_thread_id": int(TOPIC_ID),
            "text": get_message(),
            "parse_mode": "Markdown",
        },
    )
    return response.json()


def handler(request):
    """Vercel serverless function handler."""
    auth = request.headers.get("Authorization")
    cron_secret = os.environ.get("CRON_SECRET")

    if cron_secret and auth != f"Bearer {cron_secret}":
        return {"statusCode": 401, "body": "Unauthorized"}

    result = send_message()

    return {"statusCode": 200, "body": result}
