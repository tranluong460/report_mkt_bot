from datetime import datetime

from bot.config import TOPIC_ID, BUILD_TOPIC_ID, ADMIN_USER_ID, VN_TZ
from bot.store import db, get_today_reports, get_build_authorized, add_build_authorized, remove_build_authorized
from bot.telegram import send_telegram_message


def handle_debug(chat_id: int, thread_id, user_id: str) -> None:
    # Only admin can use /debug
    if ADMIN_USER_ID and user_id != str(ADMIN_USER_ID):
        send_telegram_message(chat_id, "Bạn không có quyền dùng lệnh này.", thread_id)
        return

    redis_ok = db is not None
    reports = get_today_reports() if redis_ok else {}
    today = datetime.now(VN_TZ).strftime("%Y-%m-%d")
    reporters = [r.get("reporter", uid) for uid, r in reports.items()]
    authorized = get_build_authorized()

    lines = [
        "<b>Thông tin hệ thống</b>",
        f"Redis: {'đã kết nối' if redis_ok else 'chưa kết nối'}",
        f"TOPIC_ID: <code>{TOPIC_ID}</code>",
        f"BUILD_TOPIC_ID: <code>{BUILD_TOPIC_ID}</code>",
        f"thread_id: <code>{thread_id}</code>",
        f"Báo cáo ngày {today}: <b>{len(reports)}</b> người",
    ]
    if reporters:
        lines.append("Đã nộp: " + ", ".join(reporters))
    lines.append(f"Quyền build: <b>{len(authorized)}</b> người")
    send_telegram_message(chat_id, "\n".join(lines), thread_id, parse_mode="HTML")


def handle_build_auth(chat_id: int, thread_id, user_id: str, text: str) -> None:
    """Admin command: /build_auth <user_id>"""
    if ADMIN_USER_ID and user_id != str(ADMIN_USER_ID):
        send_telegram_message(chat_id, "Chỉ admin mới dùng được lệnh này.", thread_id)
        return

    parts = text.strip().split()
    if len(parts) < 2:
        send_telegram_message(
            chat_id,
            "<b>Cú pháp:</b> <code>/build_auth &lt;user_id&gt;</code>",
            thread_id,
            parse_mode="HTML",
        )
        return

    target_id = parts[1]
    add_build_authorized(target_id)
    send_telegram_message(
        chat_id,
        f"User <code>{target_id}</code> đã được cấp quyền build.",
        thread_id,
        parse_mode="HTML",
    )


def handle_build_unauth(chat_id: int, thread_id, user_id: str, text: str) -> None:
    """Admin command: /build_unauth <user_id>"""
    if ADMIN_USER_ID and user_id != str(ADMIN_USER_ID):
        send_telegram_message(chat_id, "Chỉ admin mới dùng được lệnh này.", thread_id)
        return

    parts = text.strip().split()
    if len(parts) < 2:
        send_telegram_message(
            chat_id,
            "<b>Cú pháp:</b> <code>/build_unauth &lt;user_id&gt;</code>",
            thread_id,
            parse_mode="HTML",
        )
        return

    target_id = parts[1]
    remove_build_authorized(target_id)
    send_telegram_message(
        chat_id,
        f"User <code>{target_id}</code> đã bị xoá quyền build.",
        thread_id,
        parse_mode="HTML",
    )


def handle_help(chat_id: int, thread_id) -> None:
    """Show available commands."""
    lines = [
        "<b>Danh sách lệnh:</b>",
        "",
        "<b>Báo cáo:</b>",
        "<code>date: ...</code> - Gửi báo cáo trong report topic",
        "",
        "<b>Thành viên:</b>",
        "/follow - Đăng ký nhận thông báo",
        "/unfollow - Huỷ đăng ký",
        "/all <code>&lt;nội dung&gt;</code> - Gửi thông báo tới tất cả",
        "",
        "<b>Build:</b>",
        "/build <code>&lt;dự án&gt; [branch]</code> - Yêu cầu build",
        "/cancel <code>&lt;id&gt;</code> - Huỷ build trong hàng đợi",
        "/queue - Xem hàng đợi build",
        "/status - Xem build đang chạy",
        "/log <code>&lt;id&gt;</code> - Xem log build",
        "/build_history - Lịch sử build gần đây",
        "",
        "<b>Admin:</b>",
        "/debug - Trạng thái hệ thống",
        "/build_auth <code>&lt;user_id&gt;</code> - Cấp quyền build",
        "/build_unauth <code>&lt;user_id&gt;</code> - Xoá quyền build",
    ]
    send_telegram_message(chat_id, "\n".join(lines), thread_id, parse_mode="HTML")
