"""Tất cả template tin nhắn Telegram (HTML parse mode).

Mọi message user-facing đều tập trung ở đây. Sửa 1 chỗ, apply toàn bộ.
"""

from datetime import datetime, timedelta
from html import escape

from bot.config import VN_TZ
from bot.constants import (
    EMOJI_REPORT, EMOJI_CHECK, EMOJI_CROSS, EMOJI_HAMMER, EMOJI_HOURGLASS, EMOJI_WARNING,
    EMOJI_ROCKET, EMOJI_LIGHTNING, EMOJI_SNAIL,
    STEP_ICONS, EMOJI_WHITE_SQUARE, MAX_QUEUE_SIZE, MAX_CONCURRENT_BUILDS,
    FAST_BUILD_THRESHOLD, SLOW_BUILD_THRESHOLD,
    BOT_COMMANDS, COMMAND_GROUPS,
    DATE_FORMAT_DISPLAY, LOG_TAIL_LINES,
    SCHEDULE_JOBS, UTC_OFFSET_VN,
)

import re


def format_project_name(slug: str) -> str:
    """Chuyển slug dự án thành tên hiển thị.

    mkt-group-2025 → MKT Group
    mkt-care-2025  → MKT Care
    mkt-post-2026  → MKT Post
    """
    # Bỏ phần năm cuối (4 chữ số)
    name = re.sub(r"-\d{4}$", "", slug)
    parts = name.split("-")
    # Phần đầu viết hoa (MKT), các phần sau title case
    return " ".join(p.upper() if i == 0 else p.title() for i, p in enumerate(parts))


def duration_emoji(seconds: float) -> str:
    """Trả về emoji theo độ dài build.
    <2 phút = ⚡ fast, >10 phút = 🐌 slow, còn lại = ✅ normal."""
    if seconds < FAST_BUILD_THRESHOLD:
        return EMOJI_LIGHTNING
    if seconds > SLOW_BUILD_THRESHOLD:
        return EMOJI_SNAIL
    return EMOJI_CHECK


# ============ NHẮC NHỞ ============

def daily_reminder() -> str:
    today = datetime.now(VN_TZ).strftime(DATE_FORMAT_DISPLAY)
    return (
        f"<b>{EMOJI_REPORT} Nhắc báo cáo ngày {today}</b>\n\n"
        "Mọi người gửi báo cáo công việc hôm nay vào topic này nhé!"
    )


def weekly_reminder() -> str:
    today = datetime.now(VN_TZ)
    monday = today - timedelta(days=today.weekday())
    saturday = monday + timedelta(days=5)
    return (
        f"<b>{EMOJI_REPORT} Nhắc báo cáo tuần "
        f"{monday.strftime(DATE_FORMAT_DISPLAY)} - {saturday.strftime(DATE_FORMAT_DISPLAY)}</b>\n\n"
        "Mọi người gửi báo cáo công việc hôm nay vào topic này nhé!"
    )


# ============ REPORT ============

REPORT_FORMAT_HELP = (
    "Sai format. Cần có: `date:`, `name:`, và ít nhất 1 project `[A] Tên dự án`"
)

NO_REPORTS_TODAY = "Chưa có báo cáo nào hôm nay."
NO_DONE_TODAY = "Chưa có task done nào hôm nay."


def missing_report_alert(missing_members: dict) -> str:
    """Tạo message tag các user chưa nộp báo cáo.

    missing_members: dict {user_id: {first_name, username}}
    """
    mentions = []
    for uid, info in missing_members.items():
        name = escape(info.get("first_name", "") or "User")
        mentions.append(f'<a href="tg://user?id={uid}">{name}</a>')

    return (
        f"{EMOJI_WARNING} <b>Nhắc báo cáo hôm nay</b>\n\n"
        f"Những bạn sau chưa nộp báo cáo:\n"
        + "  " + " ".join(mentions)
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

RETRY_SYNTAX = "<b>Cú pháp:</b> <code>/retry &lt;build_id&gt;</code>"


def retry_not_found(build_id: int) -> str:
    return f"Không tìm thấy Build #{build_id} trong lịch sử."


def retry_not_failed(build_id: int) -> str:
    return f"Build #{build_id} không phải build thất bại, không thể retry."


def build_duplicate(project: str) -> str:
    return f"Dự án <code>{escape(project)}</code> đang chạy hoặc trong hàng đợi, không thể thêm lại."
BUILD_REDIS_ERROR = "Lỗi Redis, không tạo được build ID."
BUILD_NOT_IN_TOPIC = "Lệnh /build chỉ dùng được trong Build topic."


def build_no_report_projects(projects: list[str]) -> str:
    """projects: danh sách slug chưa có báo cáo ngày tương ứng."""
    names = ", ".join(escape(p) for p in projects)
    examples = ", ".join(f"<code>[X] {escape(p)}</code>" for p in projects)
    return (
        "Chưa có báo cáo ngày cho dự án: "
        f"<b>{names}</b>. Cần có ít nhất một báo cáo hôm nay có khối "
        f"{examples} khớp với dự án build (bất kỳ thành viên)."
    )


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

def build_success_caption(project: str, done_items: list,
                          duration_seconds: float = 0,
                          recent_builds: list | None = None) -> str:
    """Caption khi build thành công - liệt kê done items của project."""
    today = datetime.now(VN_TZ).strftime(DATE_FORMAT_DISPLAY)
    display_name = format_project_name(project)
    lines = [f"<b>{escape(display_name)} - {today}</b>"]
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
        f"{EMOJI_ROCKET} <b>Build #{build_id}</b> đang chạy...",
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
                    step_status: list, success: bool, error: str = None,
                    duration_seconds: float = 0) -> str:
    """Final message cho LOG topic - đã xong. Dùng emoji theo duration."""
    if success:
        icon = duration_emoji(duration_seconds)
        title = f"{icon} <b>Build #{build_id} THÀNH CÔNG</b>"
    else:
        title = f"{EMOJI_CROSS} <b>Build #{build_id} THẤT BẠI</b>"

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
    return f"<b>Build #{build_id} - {LOG_TAIL_LINES} dòng cuối:</b>\n\n<pre>{escape(tail)}</pre>"


# ============ BUILD HISTORY ============

NO_BUILD_HISTORY = "Chưa có build nào."


def build_stats(builds: list) -> str:
    """Thống kê builds từ lịch sử."""
    if not builds:
        return "Chưa có build nào để thống kê."

    total = len(builds)
    success = sum(1 for b in builds if b.get("success"))
    failed = total - success

    # Group by project
    by_project: dict[str, dict] = {}
    for b in builds:
        pj = b.get("project", "?")
        entry = by_project.setdefault(pj, {"total": 0, "success": 0, "failed": 0})
        entry["total"] += 1
        if b.get("success"):
            entry["success"] += 1
        else:
            entry["failed"] += 1

    # Group by user
    by_user: dict[str, int] = {}
    for b in builds:
        u = b.get("user_name", "?")
        by_user[u] = by_user.get(u, 0) + 1
    top_users = sorted(by_user.items(), key=lambda x: -x[1])[:5]

    lines = [
        f"<b>Thống kê build (gần đây {total})</b>",
        f"{EMOJI_CHECK} Thành công: <b>{success}</b> ({success * 100 // total}%)",
        f"{EMOJI_CROSS} Thất bại: <b>{failed}</b>",
        "",
        "<b>Theo dự án:</b>",
    ]
    for pj in sorted(by_project.keys()):
        s = by_project[pj]
        lines.append(
            f"  <code>{escape(pj)}</code>: {s['total']} "
            f"({s['success']} {EMOJI_CHECK} / {s['failed']} {EMOJI_CROSS})"
        )

    lines.append("")
    lines.append("<b>Top users:</b>")
    for user, count in top_users:
        lines.append(f"  {escape(user)}: <b>{count}</b> builds")

    return "\n".join(lines)


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


def members_list(members: dict) -> str:
    """members: dict {user_id: {first_name, username}}."""
    lines = [f"<b>Danh sách thành viên ({len(members)}):</b>", ""]
    for uid in sorted(members.keys()):
        info = members[uid]
        name = escape(info.get("first_name", ""))
        username = info.get("username", "")
        line = f"  • <code>{uid}</code> — {name}"
        if username:
            line += f" (@{escape(username)})"
        lines.append(line)
    return "\n".join(lines)


# ============ TOPIC ACL ============

TOPIC_ACL_NOT_IN_LOG = "Lệnh này chỉ dùng được trong Log topic."

TOPIC_AUTH_SYNTAX = "<b>Cú pháp:</b> <code>/topic_auth &lt;topic_id&gt; &lt;user_id&gt;</code>"
TOPIC_UNAUTH_SYNTAX = "<b>Cú pháp:</b> <code>/topic_unauth &lt;topic_id&gt; &lt;user_id&gt;</code>"
TOPIC_ACL_SYNTAX = (
    "<b>Cú pháp:</b>\n"
    "<code>/topic_acl &lt;topic_id&gt;</code> - Bật/tắt ACL cho topic\n"
    "<code>/topic_acl &lt;topic_id&gt; list</code> - Xem danh sách phân quyền"
)


def topic_auth_success(topic_id: str, user_id: str) -> str:
    return f"User <code>{user_id}</code> đã được cấp quyền nhắn tin trong topic <code>{topic_id}</code>."


def topic_unauth_success(topic_id: str, user_id: str) -> str:
    return f"User <code>{user_id}</code> đã bị xoá quyền nhắn tin trong topic <code>{topic_id}</code>."


def topic_acl_enabled(topic_id: str) -> str:
    return f"Topic <code>{topic_id}</code> đã <b>bật</b> ACL (chỉ admin + whitelist được nhắn)."


def topic_acl_disabled(topic_id: str) -> str:
    return f"Topic <code>{topic_id}</code> đã <b>tắt</b> ACL (mở cho tất cả)."


def topic_acl_list(topic_id: str, user_ids: set) -> str:
    if not user_ids:
        return f"Topic <code>{topic_id}</code> đang bật ACL nhưng chưa có ai trong whitelist (chỉ admin được nhắn)."
    lines = [f"<b>Phân quyền topic <code>{topic_id}</code>:</b>", ""]
    for uid in sorted(user_ids):
        lines.append(f"  • <code>{uid}</code>")
    return "\n".join(lines)


def topic_acl_no_restriction(topic_id: str) -> str:
    return f"Topic <code>{topic_id}</code> chưa bật ACL (mở cho tất cả)."


TOPIC_ACL_DENIED = "Bạn không có quyền nhắn tin trong topic này."


# ============ EDIT ============

EDIT_SYNTAX = "<b>Cú pháp:</b> Reply vào tin nhắn build rồi gõ:\n<code>/edit\nNội dung mới</code>"
EDIT_EMPTY = "Nội dung edit không được để trống."


# ============ HELP / DEBUG ============

def _build_help_text() -> str:
    """Build HELP_TEXT động từ BOT_COMMANDS, nhóm theo group."""
    # Group commands
    grouped: dict[str, list] = {g: [] for g in COMMAND_GROUPS}
    for cmd, _short, long_desc, group in BOT_COMMANDS:
        grouped.setdefault(group, []).append((cmd, long_desc))

    lines = ["<b>Danh sách lệnh:</b>"]
    for group in COMMAND_GROUPS:
        items = grouped.get(group)
        if not items:
            continue
        lines.append("")
        lines.append(f"<b>{group}:</b>")
        # Báo cáo group có thêm dòng đặc biệt về "date:"
        if group == "Báo cáo":
            lines.append("<code>date: ...</code> - Gửi báo cáo trong report topic (tự động follow)")
        for cmd, long_desc in items:
            lines.append(f"/{cmd} - {long_desc}")
    return "\n".join(lines)


HELP_TEXT = _build_help_text()


def _format_schedule() -> str:
    """Build schedule text từ SCHEDULE_JOBS, nhóm theo ngày, sắp theo giờ VN."""
    DAY_LABELS = {"mon-fri": "T2-T6", "sat": "T7"}
    grouped: dict[str, list] = {}
    for label, hour_utc, minute, day_of_week in SCHEDULE_JOBS:
        vn_hour = (hour_utc + UTC_OFFSET_VN) % 24
        key = DAY_LABELS.get(day_of_week, day_of_week)
        grouped.setdefault(key, []).append((vn_hour, minute, label))

    lines = []
    for day_label in DAY_LABELS.values():
        items = grouped.get(day_label)
        if not items:
            continue
        lines.append(f"  {day_label}:")
        for vn_hour, minute, label in sorted(items):
            lines.append(f"    {vn_hour:02d}:{minute:02d} - {label}")
    return "\n".join(lines)


def debug_info(redis_ok: bool, topic_id, build_topic_id, log_topic_id, thread_id,
               today: str, report_count: int, reporters: list,
               members_count: int, uptime_str: str,
               topic_acl_info: dict | None = None) -> str:
    redis_icon = EMOJI_CHECK if redis_ok else EMOJI_CROSS
    lines = [
        f"{EMOJI_HAMMER} <b>Debug - Thông tin hệ thống</b>",
        "",
        "<b>Kết nối:</b>",
        f"  {redis_icon} Redis: {'OK' if redis_ok else 'DOWN'}",
        "",
        "<b>Topics:</b>",
        f"  Report: <code>{topic_id}</code>",
        f"  Build: <code>{build_topic_id}</code>",
        f"  Log: <code>{log_topic_id}</code>",
        f"  Hiện tại: <code>{thread_id}</code>",
        "",
        f"<b>Báo cáo ngày {today}:</b>",
        f"  Đã nộp: <b>{report_count}</b> người",
    ]
    if reporters:
        lines.append(f"  {', '.join(reporters)}")
    lines += [
        "",
        "<b>Quyền:</b>",
        f"  Members: <b>{members_count}</b>",
    ]
    if topic_acl_info:
        lines.append("")
        lines.append("<b>Topic ACL:</b>")
        for tid, uids in topic_acl_info.items():
            lines.append(f"  Topic <code>{tid}</code>: <b>{len(uids)}</b> user")
    else:
        lines.append("  Topic ACL: <i>chưa thiết lập</i>")
    lines += [
        "",
        "<b>Schedule (giờ VN):</b>",
        _format_schedule(),
        "",
        f"\u23f1 Uptime: <b>{uptime_str}</b>",
    ]
    return "\n".join(lines)


def health_status(redis_ok: bool, members_count: int, running_count: int,
                  pending_count: int, uptime_str: str) -> str:
    redis_icon = EMOJI_CHECK if redis_ok else EMOJI_CROSS
    lines = [
        f"{EMOJI_HAMMER} <b>Health Check</b>",
        "",
        "<b>Kết nối:</b>",
        f"  {redis_icon} Redis: {'OK' if redis_ok else 'DOWN'}",
        "",
        "<b>Build:</b>",
        f"  {EMOJI_ROCKET} Workers: <b>{running_count}</b> đang chạy",
        f"  {EMOJI_HOURGLASS} Queue: <b>{pending_count}</b> pending",
        "",
        "<b>Thông tin:</b>",
        f"  \U0001f465 Members: <b>{members_count}</b>",
        f"  \u23f1 Uptime: <b>{uptime_str}</b>",
    ]
    return "\n".join(lines)
