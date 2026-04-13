"""Hằng số dùng chung cho toàn bộ bot."""

# ============ EMOJIS ============

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

# Rich notification emojis
EMOJI_ROCKET = "\U0001f680"       # 🚀 started
EMOJI_LIGHTNING = "\u26a1"          # ⚡ fast
EMOJI_SNAIL = "\U0001f40c"         # 🐌 slow
EMOJI_FIRE = "\U0001f525"          # 🔥 popular
EMOJI_STAR = "\u2b50"               # ⭐ milestone
EMOJI_TROPHY = "\U0001f3c6"        # 🏆 top build
EMOJI_PACKAGE = "\U0001f4e6"       # 📦 artifact

# Step status → emoji
STEP_ICONS = {
    "running": EMOJI_HOURGLASS,
    "done": EMOJI_CHECK,
    "failed": EMOJI_CROSS,
    "timeout": EMOJI_ALARM,
    "error": EMOJI_WARNING,
    "pending": EMOJI_WHITE_SQUARE,
}


# ============ REDIS KEYS ============

KEY_MEMBERS = "members"                  # Hash: user_id → {first_name, username}
KEY_REPORT_PREFIX = "reports"            # Hash: reports:YYYY-MM-DD → user_id → report
KEY_BUILD_AUTH = "build:authorized"      # Set: user_id có quyền build
KEY_BUILD_COUNTER = "build:counter"      # Int: auto-increment build_id
KEY_BUILDS_RECENT = "builds:recent"      # List: JSON của N builds gần nhất
KEY_BUILD_ACTIVE = "build:active"        # Hash: build_id → info để cleanup khi restart


# ============ TTL (giây) ============

TTL_REPORT = 172800          # 2 ngày
TTL_BUILDS_RECENT = 604800   # 7 ngày
REDIS_TIMEOUT = 5


# ============ BUILD LIMITS & TIMINGS ============

MAX_QUEUE_SIZE = 10
MAX_CONCURRENT_BUILDS = 1    # Build song song (khác project)
MAX_RECENT_BUILDS = 20       # Số builds lưu trong list history
BUILD_TIMEOUT = 3600         # 30 phút (giây)
BUILD_TIMEOUT_MINUTES = BUILD_TIMEOUT // 60
EDIT_THROTTLE_SECONDS = 2    # Tối thiểu giữa 2 lần edit cùng 1 message
LOG_TAIL_LINES = 40          # Số dòng cuối file log khi /log

# Thresholds cho emoji theo duration
FAST_BUILD_THRESHOLD = 120         # < 2 phút = ⚡ fast
SLOW_BUILD_THRESHOLD = 600         # > 10 phút = 🐌 slow
POPULAR_BUILD_THRESHOLD = 5        # ≥ 5 lần trong history = 🔥 popular


# ============ DATE FORMATS ============

DATE_FORMAT_DISPLAY = "%d/%m/%Y"          # User-facing (báo cáo, build caption)
DATE_FORMAT_KEY = "%Y-%m-%d"              # Redis key (reports:2026-04-11)
DATE_FORMAT_LOG = "%Y-%m-%d %H:%M:%S"     # Log file timestamps
DATE_FORMAT_COMPACT = "%d/%m %H:%M"       # Build record finished_at
DATE_FORMAT_JOB = "%d/%m/%Y %H:%M:%S"     # BuildJob created_at


# ============ BUILD STEPS ============
# Template - {branch} sẽ thay branch thực tế khi chạy

BUILD_STEPS = [
    ("git reset --hard", "Git reset"),
    ("git fetch --all --prune", "Git fetch"),
    ("git checkout {branch}", "Checkout {branch}"),
    ("git pull --all --prune", "Git pull"),
    ("yarn", "Yarn install"),
    ("yarn vitech", "Yarn vitech"),
    ("yarn build:win:zip", "Build Win Zip"),
]


# ============ SCHEDULE (UTC) ============
# Format: (label, hour_utc, minute, day_of_week)
# VN = UTC+7, nên 09:00 UTC = 16:00 VN

SCHEDULE_JOBS = [
    ("Nhắc nộp báo cáo ngày",  9, 0, "mon-fri"),   # 16:00 VN T2-T6
    ("Nhắc nộp báo cáo ngày",  2, 0, "sat"),        # 09:00 VN T7
    ("Nhắc nộp báo cáo tuần",  3, 0, "sat"),        # 10:00 VN T7
    ("Nhắc chưa nộp báo cáo", 10, 0, "mon-fri"),    # 17:00 VN T2-T6
    ("Nhắc chưa nộp báo cáo",  4, 0, "sat"),        # 11:00 VN T7
]

UTC_OFFSET_VN = 7  # Dùng để tính giờ VN hiển thị


# ============ REPORT PARSER SECTIONS ============

REPORT_SECTIONS = ("done", "doing", "issue", "support", "plan")
PROJECT_SECTIONS = ("done", "doing", "issue")  # Section thuộc về 1 project
GLOBAL_SECTIONS = ("support", "plan")            # Section độc lập (không thuộc project)


# ============ BOT COMMANDS ============
# Format: (command, short_desc, long_desc, group)
# - short_desc: hiện trong menu "/" Telegram (ngắn gọn)
# - long_desc: hiện trong /help (có thể chứa HTML)
# Phụ thuộc: LOG_TAIL_LINES → phải định nghĩa sau

COMMAND_GROUPS = ["Chung", "Báo cáo", "Thành viên", "Build", "Admin"]

BOT_COMMANDS = [
    # Chung
    ("help", "Danh sách lệnh", "Hiển thị danh sách lệnh này", "Chung"),
    ("health", "Kiểm tra sức khoẻ hệ thống", "Kiểm tra sức khoẻ hệ thống", "Chung"),

    # Báo cáo
    ("export", "Xuất báo cáo hôm nay ra file", "Xuất báo cáo hôm nay ra file", "Báo cáo"),

    # Thành viên
    ("follow", "Đăng ký nhận thông báo", "Đăng ký nhận thông báo (tự động khi nộp báo cáo)", "Thành viên"),
    ("unfollow", "Huỷ đăng ký thông báo", "Huỷ đăng ký", "Thành viên"),
    ("all", "Gửi thông báo tới tất cả",
     "<code>&lt;nội dung&gt;</code> Gửi thông báo tới tất cả người đã follow", "Thành viên"),

    # Build
    ("build", "Yêu cầu build (1 hoặc nhiều dự án)",
     "<code>&lt;dự án&gt; [branch]</code> hoặc <code>&lt;ds1&gt; &lt;ds2&gt; ...</code> để build song song", "Build"),
    ("retry", "Retry 1 build thất bại",
     "<code>&lt;id&gt;</code> Retry 1 build đã thất bại", "Build"),
    ("cancel", "Huỷ build trong hàng đợi",
     "<code>&lt;id&gt;</code> Huỷ build trong hàng đợi", "Build"),
    ("queue", "Xem hàng đợi build", "Xem hàng đợi build", "Build"),
    ("status", "Xem build đang chạy", "Xem build đang chạy", "Build"),
    ("log", "Xem log build",
     f"<code>&lt;id&gt;</code> Xem {LOG_TAIL_LINES} dòng log cuối của build", "Build"),
    ("build_history", f"Lịch sử {MAX_RECENT_BUILDS} build gần đây",
     f"Lịch sử {MAX_RECENT_BUILDS} build gần đây", "Build"),
    ("stats", "Thống kê build",
     "Thống kê build (tổng, theo project, top users)", "Build"),

    # Admin
    ("debug", "Trạng thái hệ thống (admin)",
     "Trạng thái hệ thống (Redis, reports, quyền)", "Admin"),
    ("build_auth", "Cấp quyền build (admin)",
     "<code>&lt;user_id&gt;</code> Cấp quyền build cho user", "Admin"),
    ("build_unauth", "Xoá quyền build (admin)",
     "<code>&lt;user_id&gt;</code> Xoá quyền build", "Admin"),
]
