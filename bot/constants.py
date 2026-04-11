"""Hằng số dùng chung cho toàn bộ bot."""

# --- Emoji ---
EMOJI_THUMBS_UP = "\U0001f44d"
EMOJI_THINKING = "\U0001f914"
EMOJI_HAMMER = "\U0001f528"
EMOJI_CHECK = "\u2705"
EMOJI_CROSS = "\u274c"
EMOJI_WARNING = "\u26a0\ufe0f"
EMOJI_HOURGLASS = "\u23f3"
EMOJI_ALARM = "\u23f0"
EMOJI_WHITE_SQUARE = "\u2b1c"
EMOJI_REPORT = "\U0001f4cb"

# --- Step status icons ---
STEP_ICONS = {
    "running": EMOJI_HOURGLASS,
    "done": EMOJI_CHECK,
    "failed": EMOJI_CROSS,
    "timeout": EMOJI_ALARM,
    "error": EMOJI_WARNING,
    "pending": EMOJI_WHITE_SQUARE,
}

# --- Redis keys ---
KEY_MEMBERS = "members"                  # Hash: user_id -> {first_name, username}
KEY_REPORT_PREFIX = "reports"            # Hash: reports:YYYY-MM-DD -> user_id -> report
KEY_BUILD_AUTH = "build:authorized"      # Set: user_id
KEY_BUILD_COUNTER = "build:counter"      # Int: auto-increment
KEY_BUILDS_RECENT = "builds:recent"      # List: JSON của 20 builds gần nhất
KEY_BUILD_ACTIVE = "build:active"        # Hash: build_id -> JSON {chat_id, message_ids, project, branch}

# --- TTL (giây) ---
TTL_REPORT = 172800          # 2 ngày
TTL_BUILDS_RECENT = 604800   # 7 ngày

# --- Số lượng builds lưu trong list ---
MAX_RECENT_BUILDS = 20

# --- Build ---
MAX_QUEUE_SIZE = 10
MAX_CONCURRENT_BUILDS = 5    # Số build chạy song song (khác project)
BUILD_TIMEOUT = 1800         # 30 phút
REDIS_TIMEOUT = 5
EDIT_THROTTLE_SECONDS = 2    # Tối thiểu giữa 2 lần edit cùng 1 message

# --- Build steps (template, {branch} sẽ thay branch thực tế) ---
BUILD_STEPS = [
    ("git reset --hard", "Git reset"),
    ("git fetch --all --prune", "Git fetch"),
    ("git checkout {branch}", "Checkout {branch}"),
    ("git pull --all --prune", "Git pull"),
    ("yarn", "Yarn install"),
    ("yarn vitech", "Yarn vitech"),
    ("yarn build:win:zip", "Build Win Zip"),
]

# --- Parser ---
REPORT_SECTIONS = ("done", "doing", "issue", "support", "plan")
PROJECT_SECTIONS = ("done", "doing", "issue")
GLOBAL_SECTIONS = ("support", "plan")
