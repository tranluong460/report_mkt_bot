"""Build commands: /build, /cancel, /queue, /status, /log, /build_history."""

import os
from html import escape

from bot.config import BUILD_TOPIC_ID, ADMIN_USER_ID, BUILD_LOG_DIR
from bot.constants import EMOJI_HAMMER, EMOJI_CHECK, EMOJI_CROSS
from bot.store import get_build_authorized, next_build_id, get_recent_builds
from bot.telegram import send_telegram_message, send_document, edit_message_media
from bot import messages
from bot.builder.queue import BuildQueue, BuildJob
from bot.builder.executor import validate_project, ensure_log_dir, get_log_tail


# ============ /build ============

def handle_build(chat_id, thread_id, message_id, text, user_id, first_name, build_queue):
    """Handle /build <project> [branch]."""
    if not _check_build_topic(chat_id, thread_id):
        return
    if not _check_build_auth(chat_id, thread_id, user_id):
        return

    parsed = _parse_build_args(chat_id, thread_id, text)
    if not parsed:
        return
    project, branch = parsed

    if not _validate_project_exists(chat_id, thread_id, project):
        return

    build_id = next_build_id()
    if build_id == 0:
        send_telegram_message(chat_id, "Lỗi Redis, không tạo được build ID.", thread_id)
        return

    job = BuildJob(
        build_id=build_id, project=project, branch=branch,
        user_id=user_id, user_name=first_name,
        chat_id=chat_id, thread_id=thread_id,
    )

    # Gửi placeholder document, lưu message_id để worker edit sau
    placeholder_path = _create_placeholder(build_id, project, branch)
    job.message_id = _send_placeholder(chat_id, thread_id, placeholder_path, build_id, project, branch)

    # Thêm vào queue
    success, position = build_queue.put(job)
    if success:
        if job.message_id is None:
            send_telegram_message(
                chat_id,
                messages.build_queued(build_id, project, branch, position),
                thread_id, parse_mode="HTML",
            )
    else:
        if job.message_id:
            edit_message_media(chat_id, job.message_id, placeholder_path,
                               "Hàng đợi đầy (tối đa 5). Vui lòng thử lại sau.")
        else:
            send_telegram_message(chat_id, "Hàng đợi đầy (tối đa 5). Vui lòng thử lại sau.", thread_id)


# ===== Validation helpers =====

def _check_build_topic(chat_id, thread_id) -> bool:
    if BUILD_TOPIC_ID and thread_id and str(thread_id) != str(BUILD_TOPIC_ID):
        send_telegram_message(chat_id, "Lệnh /build chỉ dùng được trong Build topic.", thread_id)
        return False
    return True


def _check_build_auth(chat_id, thread_id, user_id) -> bool:
    authorized = get_build_authorized()
    if user_id not in authorized and str(ADMIN_USER_ID) != str(user_id):
        send_telegram_message(
            chat_id,
            "Bạn chưa được cấp quyền build. Liên hệ admin dùng /build_auth.",
            thread_id,
        )
        return False
    return True


def _parse_build_args(chat_id, thread_id, text):
    parts = text.strip().split()
    if len(parts) < 2:
        send_telegram_message(
            chat_id,
            "<b>Cú pháp:</b> <code>/build &lt;tên dự án&gt; [branch]</code>\n"
            "Ví dụ: <code>/build mkt-care-2025</code>",
            thread_id, parse_mode="HTML",
        )
        return None
    project = parts[1]
    branch = parts[2] if len(parts) > 2 else "main"
    return project, branch


def _validate_project_exists(chat_id, thread_id, project) -> bool:
    err = validate_project(project)
    if err:
        send_telegram_message(
            chat_id,
            f"Không tìm thấy dự án <code>{escape(project)}</code> trong thư mục build.",
            thread_id, parse_mode="HTML",
        )
        return False
    return True


def _create_placeholder(build_id, project, branch) -> str:
    ensure_log_dir()
    path = os.path.join(BUILD_LOG_DIR, f"build-{build_id}.log")
    with open(path, "w", encoding="utf-8") as f:
        f.write(f"Build #{build_id} - {project} ({branch}) - đang chờ...\n")
    return path


def _send_placeholder(chat_id, thread_id, path, build_id, project, branch) -> int | None:
    caption = messages.build_waiting(build_id, project, branch)
    result = send_document(chat_id, path, caption=caption, thread_id=thread_id, parse_mode="HTML")
    return result["result"]["message_id"] if result.get("ok") else None


# ============ /cancel ============

def handle_cancel(chat_id, thread_id, text, user_id, build_queue):
    parts = text.strip().split()
    if len(parts) < 2:
        send_telegram_message(chat_id, "<b>Cú pháp:</b> <code>/cancel &lt;build_id&gt;</code>",
                              thread_id, parse_mode="HTML")
        return

    try:
        build_id = int(parts[1])
    except ValueError:
        send_telegram_message(chat_id, "Build ID phải là số.", thread_id)
        return

    if build_queue.cancel(build_id):
        send_telegram_message(chat_id, f"<b>Build #{build_id}</b> đã huỷ.",
                              thread_id, parse_mode="HTML")
    else:
        send_telegram_message(
            chat_id,
            f"Không tìm thấy Build #{build_id} trong hàng đợi (có thể đang chạy hoặc đã xong).",
            thread_id,
        )


# ============ /queue ============

def handle_queue(chat_id, thread_id, build_queue):
    status = build_queue.get_status()
    lines = ["<b>Hàng đợi build:</b>", ""]

    current = status["current"]
    if current:
        lines.append(f"Đang chạy: <b>Build #{current.build_id}</b> - {escape(current.project)} ({current.branch})")
    else:
        lines.append("Đang chạy: <i>không có</i>")

    pending = status["pending"]
    if pending:
        lines.append(f"\nChờ: <b>{len(pending)}</b> job")
        for i, job in enumerate(pending, 1):
            lines.append(f"  {i}. Build #{job.build_id} - {escape(job.project)} ({job.branch}) - {escape(job.user_name)}")
    else:
        lines.append("\nChờ: <i>không có</i>")

    send_telegram_message(chat_id, "\n".join(lines), thread_id, parse_mode="HTML")


# ============ /status ============

def handle_status(chat_id, thread_id, build_queue):
    current = build_queue.get_status()["current"]
    if not current:
        send_telegram_message(chat_id, "Hiện tại không có build nào đang chạy.", thread_id)
        return

    lines = [
        f"{EMOJI_HAMMER} <b>Đang build:</b>",
        f"  Build <b>#{current.build_id}</b>",
        f"  Dự án: <code>{escape(current.project)}</code>",
        f"  Branch: <code>{escape(current.branch)}</code>",
        f"  Bởi: {escape(current.user_name)}",
        f"  Bắt đầu: {current.created_at}",
    ]
    pending = build_queue.get_status()["pending"]
    if pending:
        lines.append(f"\nHàng đợi: <b>{len(pending)}</b> job chờ")
    send_telegram_message(chat_id, "\n".join(lines), thread_id, parse_mode="HTML")


# ============ /log ============

def handle_log(chat_id, thread_id, text):
    parts = text.strip().split()
    if len(parts) < 2:
        send_telegram_message(chat_id, "<b>Cú pháp:</b> <code>/log &lt;build_id&gt;</code>",
                              thread_id, parse_mode="HTML")
        return

    try:
        build_id = int(parts[1])
    except ValueError:
        send_telegram_message(chat_id, "Build ID phải là số.", thread_id)
        return

    log_path = os.path.join(BUILD_LOG_DIR, f"build-{build_id}.log")
    if not os.path.exists(log_path):
        send_telegram_message(chat_id, f"Không tìm thấy log cho Build #{build_id}.", thread_id)
        return

    tail = escape(get_log_tail(log_path, lines=40))
    send_telegram_message(
        chat_id,
        f"<b>Build #{build_id} - 40 dòng cuối:</b>\n\n<pre>{tail}</pre>",
        thread_id, parse_mode="HTML",
    )


# ============ /build_history ============

def handle_build_history(chat_id, thread_id):
    builds = get_recent_builds(10)
    if not builds:
        send_telegram_message(chat_id, "Chưa có build nào.", thread_id)
        return

    lines = ["<b>Lịch sử build gần đây:</b>", ""]
    for b in builds:
        icon = EMOJI_CHECK if b.get("ok") else EMOJI_CROSS
        line = (
            f"{icon} <b>#{b['id']}</b> {escape(b.get('pj', '?'))} ({b.get('b', '?')}) | "
            f"{b.get('d', '?')} | {escape(b.get('u', '?'))}"
        )
        if b.get("t"):
            line += f" | {b['t']}"
        if not b.get("ok") and b.get("e"):
            line += f"\n     <i>{escape(str(b['e'])[:80])}</i>"
        lines.append(line)

    send_telegram_message(chat_id, "\n".join(lines), thread_id, parse_mode="HTML")
