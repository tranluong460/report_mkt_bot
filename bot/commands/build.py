"""Build commands: /build, /cancel, /queue, /status, /log, /build_history."""

import os

from bot.config import BUILD_TOPIC_ID, ADMIN_USER_ID, BUILD_LOG_DIR
from bot.store import get_build_authorized, next_build_id, get_recent_builds, register_active_build
from bot.telegram import send_telegram_message, send_document, edit_message_media, delete_message
from bot import messages
from bot.builder.queue import BuildQueue, BuildJob
from bot.builder.executor import validate_project, ensure_log_dir, get_log_tail


def _send(chat_id, text, thread_id):
    """Helper gửi message HTML."""
    send_telegram_message(chat_id, text, thread_id, parse_mode="HTML")


# ============ /build ============

def handle_build(chat_id, thread_id, message_id, text, user_id, first_name, build_queue):
    if not _check_build_topic(chat_id, thread_id):
        return
    if not _check_build_auth(chat_id, thread_id, user_id):
        return

    # Parse args: trả về list tuple (project, branch)
    jobs_spec = _parse_build_args(chat_id, thread_id, text)
    if not jobs_spec:
        return

    # Multi-build: xoá command message ngay sau khi parse OK (không cần chờ)
    # Single-build: để worker xoá sau khi build xong
    is_multi = len(jobs_spec) > 1
    if is_multi:
        delete_message(chat_id, message_id)
        cmd_msg_id = None
    else:
        cmd_msg_id = message_id

    for project, branch in jobs_spec:
        _enqueue_build(chat_id, thread_id, cmd_msg_id, user_id, first_name,
                       project, branch, build_queue)


def _enqueue_build(chat_id, thread_id, command_message_id, user_id, first_name,
                   project, branch, build_queue) -> bool:
    """Tạo 1 build job và thêm vào queue. Trả về True nếu thành công."""
    build_id = next_build_id()
    if build_id == 0:
        _send(chat_id, messages.BUILD_REDIS_ERROR, thread_id)
        return False

    job = BuildJob(
        build_id=build_id, project=project, branch=branch,
        user_id=user_id, user_name=first_name,
        chat_id=chat_id, thread_id=thread_id,
        command_message_id=command_message_id,
    )

    placeholder_path = _create_placeholder(build_id, project, branch)
    job.message_id = _send_placeholder(chat_id, thread_id, placeholder_path, build_id, project, branch)

    success, _ = build_queue.put(job)
    if not success:
        if job.message_id:
            edit_message_media(chat_id, job.message_id, placeholder_path, messages.BUILD_QUEUE_FULL)
        else:
            _send(chat_id, messages.BUILD_QUEUE_FULL, thread_id)
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
        _send(chat_id, messages.BUILD_NOT_IN_TOPIC, thread_id)
        return False
    return True


def _check_build_auth(chat_id, thread_id, user_id) -> bool:
    authorized = get_build_authorized()
    if user_id not in authorized and str(ADMIN_USER_ID) != str(user_id):
        _send(chat_id, messages.BUILD_NO_AUTH, thread_id)
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
        _send(chat_id, messages.BUILD_SYNTAX, thread_id)
        return None

    # Case 1: chỉ 1 arg → single project
    if len(parts) == 1:
        project = parts[0]
        if validate_project(project):
            _send(chat_id, messages.build_project_not_found(project), thread_id)
            return None
        return [(project, "main")]

    # Case 2: 2 args → kiểm tra arg2 là project hay branch
    if len(parts) == 2:
        first, second = parts
        if validate_project(first):
            _send(chat_id, messages.build_project_not_found(first), thread_id)
            return None
        # arg2 là project hợp lệ → multi-build
        if not validate_project(second):
            return [(first, "main"), (second, "main")]
        # arg2 không phải project → branch
        return [(first, second)]

    # Case 3: 3+ args → tất cả đều phải là project
    jobs = []
    for p in parts:
        if validate_project(p):
            _send(chat_id, messages.build_project_not_found(p), thread_id)
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
    result = send_document(chat_id, path, caption=caption, thread_id=thread_id, parse_mode="HTML")
    return result["result"]["message_id"] if result.get("ok") else None


# ============ /cancel ============

def handle_cancel(chat_id, thread_id, text, user_id, build_queue):
    parts = text.strip().split()
    if len(parts) < 2:
        _send(chat_id, messages.CANCEL_SYNTAX, thread_id)
        return

    try:
        build_id = int(parts[1])
    except ValueError:
        _send(chat_id, messages.CANCEL_ID_NOT_NUMBER, thread_id)
        return

    if build_queue.cancel(build_id):
        _send(chat_id, messages.cancel_success(build_id), thread_id)
    else:
        _send(chat_id, messages.cancel_not_found(build_id), thread_id)


# ============ /queue ============

def handle_queue(chat_id, thread_id, build_queue):
    status = build_queue.get_status()
    _send(chat_id, messages.queue_status(status["running"], status["pending"]), thread_id)


# ============ /status ============

def handle_status(chat_id, thread_id, build_queue):
    status = build_queue.get_status()
    _send(chat_id, messages.status_detail(status["running"], len(status["pending"])), thread_id)


# ============ /log ============

def handle_log(chat_id, thread_id, text):
    parts = text.strip().split()
    if len(parts) < 2:
        _send(chat_id, messages.LOG_SYNTAX, thread_id)
        return

    try:
        build_id = int(parts[1])
    except ValueError:
        _send(chat_id, messages.CANCEL_ID_NOT_NUMBER, thread_id)
        return

    log_path = os.path.join(BUILD_LOG_DIR, f"build-{build_id}.log")
    if not os.path.exists(log_path):
        _send(chat_id, messages.log_not_found(build_id), thread_id)
        return

    _send(chat_id, messages.log_tail(build_id, get_log_tail(log_path, lines=40)), thread_id)


# ============ /build_history ============

def handle_build_history(chat_id, thread_id):
    builds = get_recent_builds(10)
    if not builds:
        _send(chat_id, messages.NO_BUILD_HISTORY, thread_id)
        return
    _send(chat_id, messages.build_history(builds), thread_id)
