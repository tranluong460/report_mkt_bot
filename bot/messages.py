"""Tất cả template tin nhắn Telegram (HTML parse mode)."""

from datetime import datetime, timedelta
from html import escape

from bot.config import VN_TZ
from bot.constants import EMOJI_REPORT, EMOJI_CHECK, EMOJI_CROSS, EMOJI_HAMMER, EMOJI_HOURGLASS, EMOJI_WARNING


# ============ REPORT / NHẮC NHỞ ============

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


def report_format_help() -> str:
    return "Sai format. Cần có: `date:`, `name:`, và ít nhất 1 project `[A] Tên dự án`"


# ============ MEMBER ============

def follow_success(first_name: str) -> str:
    return f"<b>{escape(first_name)}</b> đã đăng ký nhận thông báo!"


def unfollow_success(first_name: str) -> str:
    return f"<b>{escape(first_name)}</b> đã huỷ đăng ký thông báo."


def no_members() -> str:
    return "Chưa có ai đăng ký. Dùng /follow để đăng ký nhận tag."


# ============ BUILD ============

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
    from bot.constants import STEP_ICONS
    lines = [
        f"{EMOJI_HAMMER} <b>Build #{build_id}</b> đang chạy...",
        f"Dự án: <code>{escape(project)}</code> | Branch: <code>{escape(branch)}</code>",
        f"Bởi: {escape(user)} | Đã chạy: {elapsed}",
        "",
    ]
    for i, (label, status) in enumerate(step_status, 1):
        if not label:
            continue
        icon = STEP_ICONS.get(status, "\u2b1c")
        suffix = " &lt;--" if status == "running" else ""
        lines.append(f"  {icon} [{i}/{total}] {escape(label)}{suffix}")
    return "\n".join(lines)


def build_log_final(build_id: int, project: str, branch: str, user: str, duration: str,
                    step_status: list, success: bool, error: str = None) -> str:
    """Final message cho LOG topic - đã xong."""
    from bot.constants import STEP_ICONS
    title = f"{EMOJI_CHECK} <b>Build #{build_id} THÀNH CÔNG</b>" if success else f"{EMOJI_CROSS} <b>Build #{build_id} THẤT BẠI</b>"
    lines = [
        title,
        f"Dự án: <code>{escape(project)}</code> | Branch: <code>{escape(branch)}</code>",
        f"Bởi: {escape(user)} | Thời gian: <b>{duration}</b>",
        "",
    ]
    for i, (label, status) in enumerate(step_status, 1):
        if not label:
            continue
        icon = STEP_ICONS.get(status, "\u2b1c")
        lines.append(f"  {icon} [{i}/{len(step_status)}] {escape(label)}")

    if not success and error:
        lines.append(f"\n<b>Lỗi:</b> {escape(error)}")
    return "\n".join(lines)


def build_system_error(build_id: int, error: str) -> str:
    return f"{EMOJI_WARNING} <b>Build #{build_id} LỖI HỆ THỐNG:</b> {escape(error)}"


# ============ ADMIN / HELP ============

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
