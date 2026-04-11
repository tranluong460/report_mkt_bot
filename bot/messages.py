"""Tất cả template tin nhắn Telegram (HTML parse mode).

Mọi message user-facing đều tập trung ở đây. Sửa 1 chỗ, apply toàn bộ.
"""

from datetime import datetime, timedelta
from html import escape

from bot.config import VN_TZ
from bot.constants import (
    EMOJI_REPORT, EMOJI_CHECK, EMOJI_CROSS, EMOJI_HAMMER, EMOJI_HOURGLASS, EMOJI_WARNING,
    STEP_ICONS, EMOJI_WHITE_SQUARE, MAX_QUEUE_SIZE, MAX_CONCURRENT_BUILDS,
)


# ============ NHẮC NHỞ ============

def daily_reminder() -> str:
    today = datetime.now(VN_TZ).strftime("%d/%m/%Y")
    return (
        f"*{EMOJI_REPORT} Nhắc báo cáo ngày {today}*\n\n"
        "Mọi người gửi báo cáo công việc hôm nay vào topic này nhé!"
    )


def weekly_reminder() -> str:
    today = datetime.now(VN_TZ)
    monday = today - timedelta(days=today.weekday())
    saturday = monday + timedelta(days=5)
    return (
        f"*{EMOJI_REPORT} Nhắc báo cáo tuần  "
        f"{monday.strftime('%d/%m/%Y')} - {saturday.strftime('%d/%m/%Y')}*\n\n"
        "Mọi người gửi báo cáo công việc hôm nay vào topic này nhé!"
    )


# ============ REPORT ============

REPORT_FORMAT_HELP = (
    "Sai format. Cần có: `date:`, `name:`, và ít nhất 1 project `[A] Tên dự án`"
)


# ============ MEMBER ============

def follow_success(first_name: str) -> str:
    return f"<b>{escape(first_name)}</b> đã đăng ký nhận thông báo!"


def unfollow_success(first_name: str) -> str:
    return f"<b>{escape(first_name)}</b> đã huỷ đăng ký thông báo."


NO_MEMBERS = "Chưa có ai đăng ký. Dùng /follow để đăng ký nhận tag."


# ============ BUILD - Waiting / Queued ============

def build_waiting(build_id: int, project: str, branch: str) -> str:
    return (
        f"{EMOJI_HOURGLASS} <b>Build #{build_id}</b> đang chờ...\n"
        f"Dự án: <code>{escape(project)}</code>\n"
        f"Branch: <code>{escape(branch)}</code>"
    )


def build_queued(build_id: int, project: str, branch: str, position: int) -> str:
    return (
        f"<b>Build #{build_id}</b> đã thêm vào hàng đợi (vị trí #{position})\n"
        f"Dự án: <code>{escape(project)}</code>\n"
        f"Branch: <code>{escape(branch)}</code>"
    )


BUILD_QUEUE_FULL = f"Hàng đợi đầy (tối đa {MAX_QUEUE_SIZE}). Vui lòng thử lại sau."


def build_duplicate(project: str) -> str:
    return f"Dự án <code>{escape(project)}</code> đang chạy hoặc trong hàng đợi, không thể thêm lại."
BUILD_REDIS_ERROR = "Lỗi Redis, không tạo được build ID."
BUILD_NOT_IN_TOPIC = "Lệnh /build chỉ dùng được trong Build topic."
BUILD_NO_AUTH = "Bạn chưa được cấp quyền build. Liên hệ admin dùng /build_auth."

BUILD_SYNTAX = (
    "<b>Cú pháp:</b>\n"
    "<code>/build &lt;dự án&gt;</code> - build 1 dự án (branch main)\n"
    "<code>/build &lt;dự án&gt; &lt;branch&gt;</code> - build 1 dự án với branch cụ thể\n"
    "<code>/build &lt;dự án 1&gt; &lt;dự án 2&gt; ...</code> - build nhiều dự án (tất cả branch main)\n\n"
    "Ví dụ:\n"
    "<code>/build mkt-care-2025</code>\n"
    "<code>/build mkt-care-2025 develop</code>\n"
    "<code>/build mkt-care-2025 mkt-post-2026 mkt-uid-2025</code>"
)


def build_project_not_found(project: str) -> str:
    return f"Không tìm thấy dự án <code>{escape(project)}</code> trong thư mục build."


# ============ BUILD - Result ============

def build_success_caption(project: str, done_items: list) -> str:
    """Caption khi build thành công - liệt kê done items của project."""
    today = datetime.now(VN_TZ).strftime("%d/%m/%Y")
    lines = [f"<b>{escape(project)} - {today}</b>"]
    if done_items:
        for i, item in enumerate(done_items, 1):
            lines.append(f"{i}. {escape(item)}")
    else:
        lines.append("<i>Chưa có báo cáo done cho dự án này hôm nay</i>")
    return "\n".join(lines)


def build_failure_caption(build_id: int, project: str, branch: str, user: str, error: str) -> str:
    return (
        f"{EMOJI_CROSS} <b>Build #{build_id} THẤT BẠI</b>\n"
        f"Dự án: <code>{escape(project)}</code> | Branch: <code>{escape(branch)}</code>\n"
        f"Bởi: {escape(user)} | Lỗi: {escape(error)}"
    )


def build_log_header(build_id: int, project: str, branch: str, user: str, elapsed: str,
                     step_status: list, total: int) -> str:
    """Header message cho LOG topic - đang chạy."""
    lines = [
        f"{EMOJI_HAMMER} <b>Build #{build_id}</b> đang chạy...",
        f"Dự án: <code>{escape(project)}</code> | Branch: <code>{escape(branch)}</code>",
        f"Bởi: {escape(user)} | Đã chạy: {elapsed}",
        "",
    ]
    for i, (label, status) in enumerate(step_status, 1):
        if not label:
            continue
        icon = STEP_ICONS.get(status, EMOJI_WHITE_SQUARE)
        suffix = " &lt;--" if status == "running" else ""
        lines.append(f"  {icon} [{i}/{total}] {escape(label)}{suffix}")
    return "\n".join(lines)


def build_log_final(build_id: int, project: str, branch: str, user: str, duration: str,
                    step_status: list, success: bool, error: str = None) -> str:
    """Final message cho LOG topic - đã xong."""
    title = (
        f"{EMOJI_CHECK} <b>Build #{build_id} THÀNH CÔNG</b>" if success
        else f"{EMOJI_CROSS} <b>Build #{build_id} THẤT BẠI</b>"
    )
    lines = [
        title,
        f"Dự án: <code>{escape(project)}</code> | Branch: <code>{escape(branch)}</code>",
        f"Bởi: {escape(user)} | Thời gian: <b>{duration}</b>",
        "",
    ]
    for i, (label, status) in enumerate(step_status, 1):
        if not label:
            continue
        icon = STEP_ICONS.get(status, EMOJI_WHITE_SQUARE)
        lines.append(f"  {icon} [{i}/{len(step_status)}] {escape(label)}")

    if not success and error:
        lines.append(f"\n<b>Lỗi:</b> {escape(error)}")
    return "\n".join(lines)


def build_system_error(build_id: int, error: str) -> str:
    return f"{EMOJI_WARNING} <b>Build #{build_id} LỖI HỆ THỐNG:</b> {escape(error)}"


def latest_yml_caption(build_id: int, filename: str) -> str:
    return f"Build #{build_id} - {filename}"


def placeholder_log_content(build_id: int, project: str, branch: str) -> str:
    return f"Build #{build_id} - {project} ({branch}) - đang chờ...\n"


def build_interrupted(build_id: int, project: str, branch: str) -> str:
    return (
        f"{EMOJI_WARNING} <b>Build #{build_id} BỊ GIÁN ĐOẠN</b>\n"
        f"Dự án: <code>{escape(project)}</code> | Branch: <code>{escape(branch)}</code>\n"
        f"Bot đã restart. Vui lòng gửi lại lệnh /build để chạy lại."
    )


# ============ CANCEL ============

CANCEL_SYNTAX = "<b>Cú pháp:</b> <code>/cancel &lt;build_id&gt;</code>"
CANCEL_ID_NOT_NUMBER = "Build ID phải là số."


def cancel_success(build_id: int) -> str:
    return f"<b>Build #{build_id}</b> đã huỷ."


def cancel_not_found(build_id: int) -> str:
    return f"Không tìm thấy Build #{build_id} trong hàng đợi (có thể đang chạy hoặc đã xong)."


# ============ QUEUE / STATUS ============

def queue_status(running: list, pending: list) -> str:
    lines = ["<b>Hàng đợi build:</b>", ""]
    if running:
        lines.append(f"Đang chạy: <b>{len(running)}</b>/{MAX_CONCURRENT_BUILDS} build")
        for job in running:
            lines.append(f"  • Build #{job.build_id} - {escape(job.project)} ({job.branch})")
    else:
        lines.append("Đang chạy: <i>không có</i>")

    if pending:
        lines.append(f"\nChờ: <b>{len(pending)}</b>/{MAX_QUEUE_SIZE} job")
        for i, job in enumerate(pending, 1):
            lines.append(
                f"  {i}. Build #{job.build_id} - {escape(job.project)} "
                f"({job.branch}) - {escape(job.user_name)}"
            )
    else:
        lines.append("\nChờ: <i>không có</i>")
    return "\n".join(lines)


def status_detail(running: list, pending_count: int) -> str:
    if not running:
        return NO_RUNNING_BUILD

    lines = [f"{EMOJI_HAMMER} <b>Đang build ({len(running)}/{MAX_CONCURRENT_BUILDS}):</b>"]
    for job in running:
        lines.append("")
        lines.append(f"  Build <b>#{job.build_id}</b>")
        lines.append(f"  Dự án: <code>{escape(job.project)}</code>")
        lines.append(f"  Branch: <code>{escape(job.branch)}</code>")
        lines.append(f"  Bởi: {escape(job.user_name)}")
        lines.append(f"  Bắt đầu: {job.created_at}")
    if pending_count:
        lines.append(f"\nHàng đợi: <b>{pending_count}</b>/{MAX_QUEUE_SIZE} job chờ")
    return "\n".join(lines)


NO_RUNNING_BUILD = "Hiện tại không có build nào đang chạy."


# ============ LOG ============

LOG_SYNTAX = "<b>Cú pháp:</b> <code>/log &lt;build_id&gt;</code>"


def log_not_found(build_id: int) -> str:
    return f"Không tìm thấy log cho Build #{build_id}."


def log_tail(build_id: int, tail: str) -> str:
    return f"<b>Build #{build_id} - 40 dòng cuối:</b>\n\n<pre>{escape(tail)}</pre>"


# ============ BUILD HISTORY ============

NO_BUILD_HISTORY = "Chưa có build nào."


def build_history(builds: list) -> str:
    lines = ["<b>Lịch sử build gần đây:</b>", ""]
    for b in builds:
        icon = EMOJI_CHECK if b.get("success") else EMOJI_CROSS
        line = (
            f"{icon} <b>#{b['id']}</b> {escape(b.get('project', '?'))} "
            f"({b.get('branch', '?')}) | {b.get('duration', '?')} | "
            f"{escape(b.get('user_name', '?'))}"
        )
        if b.get("finished_at"):
            line += f" | {b['finished_at']}"
        if not b.get("success") and b.get("error"):
            line += f"\n     <i>{escape(str(b['error'])[:80])}</i>"
        lines.append(line)
    return "\n".join(lines)


# ============ ADMIN ============

ADMIN_ONLY = "Chỉ admin mới dùng được lệnh này."

BUILD_AUTH_SYNTAX = "<b>Cú pháp:</b> <code>/build_auth &lt;user_id&gt;</code>"
BUILD_UNAUTH_SYNTAX = "<b>Cú pháp:</b> <code>/build_unauth &lt;user_id&gt;</code>"


def build_auth_success(user_id: str) -> str:
    return f"User <code>{user_id}</code> đã được cấp quyền build."


def build_unauth_success(user_id: str) -> str:
    return f"User <code>{user_id}</code> đã bị xoá quyền build."


# ============ HELP / DEBUG ============

HELP_TEXT = """<b>Danh sách lệnh:</b>

<b>Chung:</b>
/help - Hiển thị danh sách lệnh này

<b>Báo cáo:</b>
<code>date: ...</code> - Gửi báo cáo trong report topic

<b>Thành viên:</b>
/follow - Đăng ký nhận thông báo
/unfollow - Huỷ đăng ký
/all <code>&lt;nội dung&gt;</code> - Gửi thông báo tới tất cả người đã follow

<b>Build:</b>
/build <code>&lt;dự án&gt; [branch]</code> - Yêu cầu build
/cancel <code>&lt;id&gt;</code> - Huỷ build trong hàng đợi
/queue - Xem hàng đợi build
/status - Xem build đang chạy
/log <code>&lt;id&gt;</code> - Xem 40 dòng log cuối của build
/build_history - Lịch sử 10 build gần đây

<b>Admin:</b>
/debug - Trạng thái hệ thống (Redis, reports, quyền)
/build_auth <code>&lt;user_id&gt;</code> - Cấp quyền build cho user
/build_unauth <code>&lt;user_id&gt;</code> - Xoá quyền build"""


def debug_info(redis_ok: bool, topic_id, build_topic_id, thread_id,
               today: str, report_count: int, reporters: list, auth_count: int) -> str:
    lines = [
        "<b>Thông tin hệ thống</b>",
        f"Redis: {'đã kết nối' if redis_ok else 'chưa kết nối'}",
        f"TOPIC_ID: <code>{topic_id}</code>",
        f"BUILD_TOPIC_ID: <code>{build_topic_id}</code>",
        f"thread_id: <code>{thread_id}</code>",
        f"Báo cáo ngày {today}: <b>{report_count}</b> người",
    ]
    if reporters:
        lines.append("Đã nộp: " + ", ".join(reporters))
    lines.append(f"Quyền build: <b>{auth_count}</b> người")
    return "\n".join(lines)
