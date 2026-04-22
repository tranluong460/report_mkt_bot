"""Build commands: /build, /cancel, /queue, /status, /log, /build_history."""

import os
from threading import Timer

from bot.config import BUILD_TOPIC_ID, BUILD_LOG_DIR
from bot.constants import LOG_TAIL_LINES, MAX_RECENT_BUILDS, TTL_TOPIC_ACL_WARNING
from bot.core.store import (
    next_build_id, get_recent_builds,
    register_active_build,
)
from bot.core.telegram import send_html, send_document, edit_message_media, edit_message_caption, delete_message
from bot import messages
from bot.builder.queue import BuildJob
from bot.builder.executor import validate_project, ensure_log_dir, get_log_tail


# ============ helpers ============

def _send_ephemeral(chat_id, text, thread_id):
    """Gửi tin nhắn tạm, tự xóa sau 3s."""
    result = send_html(chat_id, text, thread_id)
    msg_id = result.get("result", {}).get("message_id") if result.get("ok") else None
    if msg_id:
        Timer(TTL_TOPIC_ACL_WARNING, delete_message, [chat_id, msg_id]).start()


# ============ /build ============

def handle_build(chat_id, thread_id, message_id, text, user_id, first_name, build_queue):
    # Xoá command message ngay lập tức
    delete_message(chat_id, message_id)

    if not _check_build_topic(chat_id, thread_id):
        return

    # Parse args: trả về list tuple (project, branch)
    jobs_spec = _parse_build_args(chat_id, thread_id, text)
    if not jobs_spec:
        return

    for project, branch in jobs_spec:
        _enqueue_build(chat_id, thread_id, None, user_id, first_name,
                       project, branch, build_queue)


def _enqueue_build(chat_id, thread_id, command_message_id, user_id, first_name,
                   project, branch, build_queue) -> bool:
    """Tạo 1 build job và thêm vào queue. Trả về True nếu thành công."""
    build_id = next_build_id()
    if build_id == 0:
        _send_ephemeral(chat_id, messages.BUILD_REDIS_ERROR, thread_id)
        return False

    job = BuildJob(
        build_id=build_id, project=project, branch=branch,
        user_id=user_id, user_name=first_name,
        chat_id=chat_id, thread_id=thread_id,
        command_message_id=command_message_id,
    )

    # Check duplicate TRƯỚC khi gửi placeholder (tránh spam message)
    if build_queue.is_project_active(project):
        _send_ephemeral(chat_id, messages.build_duplicate(project), thread_id)
        return False

    placeholder_path = _create_placeholder(build_id, project, branch)
    job.message_id = _send_placeholder(chat_id, thread_id, placeholder_path, build_id, project, branch)

    success, position = build_queue.put(job)
    if not success:
        if position == -1:
            # Duplicate (race condition - project vừa được thêm)
            msg = messages.build_duplicate(project)
        else:
            msg = messages.BUILD_QUEUE_FULL
        if job.message_id:
            edit_message_media(chat_id, job.message_id, placeholder_path, msg)
        else:
            send_html(chat_id, msg, thread_id)
        return False

    # Register active build ngay từ lúc pending (để cleanup nếu restart lúc còn pending)
    register_active_build(build_id, {
        "chat_id": chat_id,
        "build_msg_id": job.message_id,
        "log_msg_id": None,
        "log_thread_id": None,
        "build_thread_id": thread_id,
        "project": project,
        "branch": branch,
    })
    return True


# ===== Validation helpers =====

def _check_build_topic(chat_id, thread_id) -> bool:
    if BUILD_TOPIC_ID and thread_id and str(thread_id) != str(BUILD_TOPIC_ID):
        _send_ephemeral(chat_id, messages.BUILD_NOT_IN_TOPIC, thread_id)
        return False
    return True


def _parse_build_args(chat_id, thread_id, text) -> list | None:
    """Parse /build args. Trả về list (project, branch) hoặc None nếu lỗi.

    Rules:
    - /build p1                → [(p1, main)]
    - /build p1 branch         → [(p1, branch)]  nếu branch KHÔNG phải project
    - /build p1 p2             → [(p1, main), (p2, main)]  nếu p2 LÀ project
    - /build p1 p2 p3          → [(p1, main), (p2, main), (p3, main)]
    """
    parts = text.strip().split()[1:]  # bỏ /build
    if not parts:
        _send_ephemeral(chat_id, messages.BUILD_SYNTAX, thread_id)
        return None

    # Case 1: chỉ 1 arg → single project
    if len(parts) == 1:
        project = parts[0]
        if validate_project(project):
            _send_ephemeral(chat_id, messages.build_project_not_found(project), thread_id)
            return None
        return [(project, "main")]

    # Case 2: 2 args → kiểm tra arg2 là project hay branch
    if len(parts) == 2:
        first, second = parts
        if validate_project(first):
            _send_ephemeral(chat_id, messages.build_project_not_found(first), thread_id)
            return None
        # arg2 là project hợp lệ → multi-build
        if not validate_project(second):
            return [(first, "main"), (second, "main")]
        # arg2 không phải project → branch
        return [(first, second)]

    # Case 3: 3+ args → tất cả đều phải là project
    seen = set()
    jobs = []
    for p in parts:
        if p in seen:
            continue  # Bỏ qua duplicate
        seen.add(p)
        if validate_project(p):
            _send_ephemeral(chat_id, messages.build_project_not_found(p), thread_id)
            return None
        jobs.append((p, "main"))
    return jobs


def _create_placeholder(build_id, project, branch) -> str:
    ensure_log_dir()
    path = os.path.join(BUILD_LOG_DIR, f"build-{build_id}.log")
    with open(path, "w", encoding="utf-8") as f:
        f.write(messages.placeholder_log_content(build_id, project, branch))
    return path


def _send_placeholder(chat_id, thread_id, path, build_id, project, branch) -> int | None:
    caption = messages.build_waiting(build_id, project, branch)
    reply_markup = {
        "inline_keyboard": [[
            {"text": "\u274c Huỷ build", "callback_data": f"cancel:{build_id}"}
        ]]
    }
    result = send_document(
        chat_id, path, caption=caption,
        thread_id=thread_id, parse_mode="HTML",
        reply_markup=reply_markup,
    )
    return result["result"]["message_id"] if result.get("ok") else None


# ============ /retry ============

def handle_retry(chat_id, thread_id, message_id, text, user_id, first_name, build_queue):
    """Retry 1 build thất bại. Tìm trong build history → tạo job mới cùng project/branch."""
    if not _check_build_topic(chat_id, thread_id):
        return

    parts = text.strip().split()
    if len(parts) < 2:
        send_html(chat_id, messages.RETRY_SYNTAX, thread_id)
        return

    try:
        target_id = int(parts[1])
    except ValueError:
        send_html(chat_id, messages.CANCEL_ID_NOT_NUMBER, thread_id)
        return

    # Tìm trong history
    history = get_recent_builds(MAX_RECENT_BUILDS)
    target = next((b for b in history if b.get("id") == target_id), None)
    if not target:
        send_html(chat_id, messages.retry_not_found(target_id), thread_id)
        return
    if target.get("success"):
        send_html(chat_id, messages.retry_not_failed(target_id), thread_id)
        return

    project = target.get("project")
    branch = target.get("branch", "main")

    # Xoá message /retry của user ngay
    delete_message(chat_id, message_id)

    # Xoá tin nhắn build lỗi cũ
    old_msg_id = target.get("message_id")
    if old_msg_id:
        delete_message(chat_id, old_msg_id)

    # Enqueue như build bình thường
    _enqueue_build(chat_id, thread_id, None, user_id, first_name,
                   project, branch, build_queue)


def handle_retry_callback(chat_id, msg_id, build_id, user_id, first_name, build_queue):
    """Retry qua inline button. Trả về (success, message)."""
    history = get_recent_builds(MAX_RECENT_BUILDS)
    target = next((b for b in history if b.get("id") == build_id), None)
    if not target:
        return False, f"Không tìm thấy Build #{build_id}"
    if target.get("success"):
        return False, f"Build #{build_id} không phải build lỗi"

    project = target.get("project")
    branch = target.get("branch", "main")
    thread_id = BUILD_TOPIC_ID and int(BUILD_TOPIC_ID)

    # Xoá tin nhắn build lỗi cũ
    delete_message(chat_id, msg_id)

    _enqueue_build(chat_id, thread_id, None, user_id, first_name,
                   project, branch, build_queue)
    return True, f"Đang retry Build #{build_id}"


# ============ /cancel ============

def handle_cancel(chat_id, thread_id, text, user_id, build_queue):
    parts = text.strip().split()
    if len(parts) < 2:
        send_html(chat_id, messages.CANCEL_SYNTAX, thread_id)
        return

    try:
        build_id = int(parts[1])
    except ValueError:
        send_html(chat_id, messages.CANCEL_ID_NOT_NUMBER, thread_id)
        return

    if build_queue.cancel(build_id):
        send_html(chat_id, messages.cancel_success(build_id), thread_id)
    else:
        send_html(chat_id, messages.cancel_not_found(build_id), thread_id)


# ============ /queue ============

def handle_queue(chat_id, thread_id, build_queue):
    status = build_queue.get_status()
    send_html(chat_id, messages.queue_status(status["running"], status["pending"]), thread_id)


# ============ /status ============

def handle_status(chat_id, thread_id, build_queue):
    status = build_queue.get_status()
    send_html(chat_id, messages.status_detail(status["running"], len(status["pending"])), thread_id)


# ============ /log ============

def handle_log(chat_id, thread_id, text):
    parts = text.strip().split()
    if len(parts) < 2:
        send_html(chat_id, messages.LOG_SYNTAX, thread_id)
        return

    try:
        build_id = int(parts[1])
    except ValueError:
        send_html(chat_id, messages.CANCEL_ID_NOT_NUMBER, thread_id)
        return

    log_path = os.path.join(BUILD_LOG_DIR, f"build-{build_id}.log")
    if not os.path.exists(log_path):
        send_html(chat_id, messages.log_not_found(build_id), thread_id)
        return

    send_html(chat_id, messages.log_tail(build_id, get_log_tail(log_path, lines=LOG_TAIL_LINES)), thread_id)


# ============ /build_history ============

def handle_build_history(chat_id, thread_id):
    builds = get_recent_builds(10)
    if not builds:
        send_html(chat_id, messages.NO_BUILD_HISTORY, thread_id)
        return
    send_html(chat_id, messages.build_history(builds), thread_id)


# ============ /stats ============

def handle_stats(chat_id, thread_id):
    builds = get_recent_builds(MAX_RECENT_BUILDS)
    send_html(chat_id, messages.build_stats(builds), thread_id)


# ============ /edit ============

def handle_edit(chat_id, thread_id, message_id, text, reply_to_message_id):
    """Edit caption của tin nhắn build. User reply vào tin nhắn build rồi gõ /edit + nội dung mới."""
    if not reply_to_message_id:
        send_html(chat_id, messages.EDIT_SYNTAX, thread_id)
        return

    # Lấy nội dung sau /edit (bỏ dòng đầu nếu chỉ có "/edit")
    new_caption = text.split("\n", 1)[1].strip() if "\n" in text else text.split(None, 1)[1] if len(text.split()) > 1 else ""
    # Nội dung trống → xóa caption (giữ file)
    edit_message_caption(chat_id, reply_to_message_id, new_caption or "")
    delete_message(chat_id, message_id)
