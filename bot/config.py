import os
from datetime import timezone, timedelta
from dotenv import load_dotenv

load_dotenv()

# --- Telegram ---
BOT_TOKEN = os.environ.get("BOT_TOKEN")
GROUP_CHAT_ID = os.environ.get("GROUP_CHAT_ID")
TOPIC_ID = os.environ.get("TOPIC_ID")
WEEKLY_TOPIC_ID = os.environ.get("WEEKLY_TOPIC_ID")
BUILD_TOPIC_ID = os.environ.get("BUILD_TOPIC_ID")
LOG_TOPIC_ID = os.environ.get("LOG_TOPIC_ID")
ADMIN_USER_ID = os.environ.get("ADMIN_USER_ID")

# --- Redis ---
KV_REDIS_URL = os.environ.get("KV_REDIS_URL")

# --- Build ---
BUILD_LOG_DIR = os.environ.get("BUILD_LOG_DIR", "D:/Code/builds/logs")
BUILD_PROJECT_DIR = os.environ.get("BUILD_PROJECT_DIR", "D:/Code")

# --- Telegram API ---
TELEGRAM_LOCAL_API = os.environ.get("TELEGRAM_LOCAL_API", "")
if TELEGRAM_LOCAL_API:
    TELEGRAM_API = f"{TELEGRAM_LOCAL_API}/bot{BOT_TOKEN}"
else:
    TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}"

# --- Timezone Vietnam (UTC+7) ---
VN_TZ = timezone(timedelta(hours=7))

# --- Redis keys ---
KV_KEY = "members"
REPORT_KEY_PREFIX = "reports"
BUILD_AUTH_KEY = "build:authorized"
BUILD_COUNTER_KEY = "build:counter"
BUILD_PREFIX = "build"


def validate_config():
    """Validate tất cả biến môi trường bắt buộc khi khởi động."""
    required = {
        "BOT_TOKEN": BOT_TOKEN,
        "GROUP_CHAT_ID": GROUP_CHAT_ID,
        "TOPIC_ID": TOPIC_ID,
        "WEEKLY_TOPIC_ID": WEEKLY_TOPIC_ID,
        "BUILD_TOPIC_ID": BUILD_TOPIC_ID,
        "LOG_TOPIC_ID": LOG_TOPIC_ID,
        "ADMIN_USER_ID": ADMIN_USER_ID,
        "KV_REDIS_URL": KV_REDIS_URL,
        "BUILD_LOG_DIR": BUILD_LOG_DIR,
        "BUILD_PROJECT_DIR": BUILD_PROJECT_DIR,
    }
    missing = [k for k, v in required.items() if not v]
    if missing:
        raise RuntimeError(f"Thiếu biến môi trường: {', '.join(missing)}")
