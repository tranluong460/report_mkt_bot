from html import escape

import os

from bot.config import BUILD_TOPIC_ID, ADMIN_USER_ID, BUILD_LOG_DIR
from bot.store import get_build_authorized, next_build_id, get_recent_builds
from bot.telegram import send_telegram_message, send_media_group
from bot.builder.queue import BuildQueue, BuildJob
from bot.builder.executor import validate_project, ensure_log_dir


def handle_build(
    chat_id: int,
    thread_id,
    message_id: int,
    text: str,
    user_id: str,
    first_name: str,
    build_queue: BuildQueue,
) -> None:
    """Handle /build <project> [branch] command."""
    # Kiểm tra topic
    if BUILD_TOPIC_ID and thread_id and str(thread_id) != str(BUILD_TOPIC_ID):
        send_telegram_message(chat_id, "Lệnh /build chỉ dùng được trong Build topic.", thread_id)
        return

    # Kiểm tra quyền
    authorized = get_build_authorized()
    if user_id not in authorized and str(ADMIN_USER_ID) != str(user_id):
        send_telegram_message(
            chat_id,
            "Bạn chưa được cấp quyền build. Liên hệ admin dùng /build_auth.",
            thread_id,
        )
        return

    # Parse arguments
    parts = text.strip().split()
    if len(parts) < 2:
        send_telegram_message(
            chat_id,
            "<b>Cú pháp:</b> <code>/build &lt;tên dự án&gt; [branch]</code>\n"
            "Ví dụ: <code>/build mkt-care-2025</code>\n"
            "Ví dụ: <code>/build mkt-care-2025 develop</code>",
            thread_id,
            parse_mode="HTML",
        )
        return

    project = parts[1]
    branch = parts[2] if len(parts) > 2 else "main"

    # Kiểm tra thư mục dự án
    err = validate_project(project)
    if err:
        send_telegram_message(
            chat_id,
            f"Không tìm thấy dự án <code>{escape(project)}</code> trong thư mục build.",
            thread_id,
            parse_mode="HTML",
        )
        return

    # Tạo build ID
    build_id = next_build_id()
    if build_id == 0:
        send_telegram_message(chat_id, "Lỗi Redis, không tạo được build ID.", thread_id)
        return

    # Tạo job
    job = BuildJob(
        build_id=build_id,
        project=project,
        branch=branch,
        user_id=user_id,
        user_name=first_name,
        chat_id=chat_id,
        thread_id=thread_id,
    )

    # Gửi media group placeholder (zip + latest.yml) vào BUILD topic
    # Worker sẽ dùng editMessageMedia để thay file thật
    ensure_log_dir()
    placeholder_zip = os.path.join(BUILD_LOG_DIR, f"{project}.zip")
    placeholder_yml = os.path.join(BUILD_LOG_DIR, f"latest.yml")
    with open(placeholder_zip, "w", encoding="utf-8") as f:
        f.write(f"Build #{build_id} - {project} ({branch}) - đang chờ...\n")
    with open(placeholder_yml, "w", encoding="utf-8") as f:
        f.write(f"Build #{build_id} - đang chờ...\n")

    caption = (
        f"\u23f3 <b>Build #{build_id}</b> đang chờ...\n"
        f"Dự án: <code>{escape(project)}</code>\n"
        f"Branch: <code>{escape(branch)}</code>"
    )
    result = send_media_group(
        chat_id, [placeholder_zip, placeholder_yml],
        caption=caption, thread_id=thread_id,
    )
    # sendMediaGroup trả về list messages, lưu cả 2 message_id
    if result.get("ok") and result.get("result"):
        messages = result["result"]
        job.message_id = messages[0]["message_id"]       # zip message
        job.message_id_2 = messages[1]["message_id"]     # yml message

    # Thêm vào queue
    success, position = build_queue.put(job)
    if not success:
        if job.message_id:
            from bot.telegram import edit_message_media, delete_message
            edit_message_media(chat_id, job.message_id, placeholder_zip,
                               "Hàng đợi đầy (tối đa 5). Vui lòng thử lại sau.")
            if job.message_id_2:
                delete_message(chat_id, job.message_id_2)
        else:
            send_telegram_message(chat_id, "Hàng đợi đầy (tối đa 5). Vui lòng thử lại sau.", thread_id)


def handle_cancel(chat_id: int, thread_id, text: str, user_id: str, build_queue: BuildQueue) -> None:
    """Handle /cancel <build_id> command."""
    parts = text.strip().split()
    if len(parts) < 2:
        send_telegram_message(
            chat_id,
            "<b>Cú pháp:</b> <code>/cancel &lt;build_id&gt;</code>",
            thread_id,
            parse_mode="HTML",
        )
        return

    try:
        build_id = int(parts[1])
    except ValueError:
        send_telegram_message(chat_id, "Build ID phải là số.", thread_id)
        return

    if build_queue.cancel(build_id):
        send_telegram_message(
            chat_id,
            f"<b>Build #{build_id}</b> đã huỷ.",
            thread_id,
            parse_mode="HTML",
        )
    else:
        send_telegram_message(
            chat_id,
            f"Không tìm thấy Build #{build_id} trong hàng đợi (có thể đang chạy hoặc đã xong).",
            thread_id,
        )


def handle_queue(chat_id: int, thread_id, build_queue: BuildQueue) -> None:
    """Handle /queue command."""
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


def handle_build_history(chat_id: int, thread_id) -> None:
    """Handle /build_history command."""
    builds = get_recent_builds(10)
    if not builds:
        send_telegram_message(chat_id, "Chưa có build nào.", thread_id)
        return

    lines = ["<b>Lịch sử build gần đây:</b>", ""]
    for b in builds:
        icon = "\u2705" if b.get("ok") else "\u274c"
        pj = b.get("pj", "?")
        br = b.get("b", "?")
        dur = b.get("d", "?")
        user = b.get("u", "?")
        ts = b.get("t", "")
        err = b.get("e", "")

        line = f"{icon} <b>#{b['id']}</b> {escape(pj)} ({br}) | {dur} | {escape(user)}"
        if ts:
            line += f" | {ts}"
        if not b.get("ok") and err:
            line += f"\n     <i>{escape(str(err)[:80])}</i>"
        lines.append(line)

    send_telegram_message(chat_id, "\n".join(lines), thread_id, parse_mode="HTML")


def handle_log(chat_id: int, thread_id, text: str) -> None:
    """Handle /log <build_id> - xem log của build."""
    from bot.builder.executor import get_log_tail, BUILD_LOG_DIR
    import os

    parts = text.strip().split()
    if len(parts) < 2:
        send_telegram_message(
            chat_id,
            "<b>Cú pháp:</b> <code>/log &lt;build_id&gt;</code>",
            thread_id,
            parse_mode="HTML",
        )
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
        thread_id,
        parse_mode="HTML",
    )


def handle_status(chat_id: int, thread_id, build_queue: BuildQueue) -> None:
    """Handle /status - xem build đang chạy."""
    status = build_queue.get_status()
    current = status["current"]

    if not current:
        send_telegram_message(chat_id, "Hiện tại không có build nào đang chạy.", thread_id)
        return

    lines = [
        f"\U0001f528 <b>Đang build:</b>",
        f"  Build <b>#{current.build_id}</b>",
        f"  Dự án: <code>{escape(current.project)}</code>",
        f"  Branch: <code>{escape(current.branch)}</code>",
        f"  Bởi: {escape(current.user_name)}",
        f"  Bắt đầu: {current.created_at}",
    ]

    pending = status["pending"]
    if pending:
        lines.append(f"\nHàng đợi: <b>{len(pending)}</b> job chờ")

    send_telegram_message(chat_id, "\n".join(lines), thread_id, parse_mode="HTML")
