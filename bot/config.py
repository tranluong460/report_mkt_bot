import os
from datetime import timezone, timedelta
from dotenv import load_dotenv

load_dotenv()

def _int_env(key: str) -> int | None:
    """Đọc env var dạng int, None nếu không có."""
    val = os.environ.get(key)
    if val is None or val == "":
        return None
    try:
        return int(val)
    except ValueError:
        return None


# --- Telegram ---
BOT_TOKEN = os.environ.get("BOT_TOKEN")
GROUP_CHAT_ID = _int_env("GROUP_CHAT_ID")
TOPIC_ID = _int_env("TOPIC_ID")
WEEKLY_TOPIC_ID = _int_env("WEEKLY_TOPIC_ID")
BUILD_TOPIC_ID = _int_env("BUILD_TOPIC_ID")
LOG_TOPIC_ID = _int_env("LOG_TOPIC_ID")
GENERAL_TOPIC_ID = _int_env("GENERAL_TOPIC_ID")
# ADMIN_USER_ID vẫn để string vì dùng so sánh với user_id (cũng là string)
ADMIN_USER_ID = os.environ.get("ADMIN_USER_ID")

# --- Redis ---
KV_REDIS_URL = os.environ.get("KV_REDIS_URL")

# --- Build ---
BUILD_LOG_DIR = os.environ.get("BUILD_LOG_DIR", "D:/Code/builds/logs")
BUILD_PROJECT_DIR = os.environ.get("BUILD_PROJECT_DIR", "D:/Code")

# --- Vitech Task API ---
VITECH_API_URL = os.environ.get("VITECH_API_URL", "https://api-dev.vitechgroup.vn")
VITECH_API_EMAIL = os.environ.get("VITECH_API_EMAIL")
VITECH_API_PASSWORD = os.environ.get("VITECH_API_PASSWORD")
VITECH_WEB_URL = os.environ.get("VITECH_WEB_URL", "https://dev.vitechgroup.vn/tasks")

# --- Telegram API ---
TELEGRAM_LOCAL_API = os.environ.get("TELEGRAM_LOCAL_API", "")
if TELEGRAM_LOCAL_API:
    TELEGRAM_API = f"{TELEGRAM_LOCAL_API}/bot{BOT_TOKEN}"
else:
    TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}"

# --- Timezone Vietnam (UTC+7) ---
VN_TZ = timezone(timedelta(hours=7))


def validate_config():
    """Validate tất cả biến môi trường bắt buộc khi khởi động."""
    required = {
        "BOT_TOKEN": BOT_TOKEN,
        "GROUP_CHAT_ID": GROUP_CHAT_ID,
        "TOPIC_ID": TOPIC_ID,
        "WEEKLY_TOPIC_ID": WEEKLY_TOPIC_ID,
        "BUILD_TOPIC_ID": BUILD_TOPIC_ID,
        "LOG_TOPIC_ID": LOG_TOPIC_ID,
        "GENERAL_TOPIC_ID": GENERAL_TOPIC_ID,
        "ADMIN_USER_ID": ADMIN_USER_ID,
        "KV_REDIS_URL": KV_REDIS_URL,
        "BUILD_LOG_DIR": BUILD_LOG_DIR,
        "BUILD_PROJECT_DIR": BUILD_PROJECT_DIR,
        "VITECH_API_EMAIL": VITECH_API_EMAIL,
        "VITECH_API_PASSWORD": VITECH_API_PASSWORD,
    }
    missing = [k for k, v in required.items() if not v]
    if missing:
        raise RuntimeError(f"Thiếu biến môi trường: {', '.join(missing)}")
