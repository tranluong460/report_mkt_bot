import os
from datetime import timezone, timedelta

BOT_TOKEN = os.environ.get("BOT_TOKEN")
GROUP_CHAT_ID = os.environ.get("GROUP_CHAT_ID")
TOPIC_ID = os.environ.get("TOPIC_ID")
BUILD_TOPIC_ID = os.environ.get("BUILD_TOPIC_ID", "258")
CRON_SECRET = os.environ.get("CRON_SECRET")
KV_REDIS_URL = os.environ.get("KV_REDIS_URL")

TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}"

VN_TZ = timezone(timedelta(hours=7))
KV_KEY = "members"
REPORT_KEY_PREFIX = "reports"
