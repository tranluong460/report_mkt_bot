"""Build commands: /build, /cancel, /queue, /status, /log, /build_history."""

import os

from bot.config import BUILD_TOPIC_ID, ADMIN_USER_ID, BUILD_LOG_DIR
from bot.store import get_build_authorized, next_build_id, get_recent_builds
from bot.telegram import send_telegram_message, send_document, edit_message_media
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

    parsed = _parse_build_args(chat_id, thread_id, text)
    if not parsed:
        return
    project, branch = parsed

    if not _validate_project_exists(chat_id, thread_id, project):
        return

    build_id = next_build_id()
    if build_id == 0:
        _send(chat_id, messages.BUILD_REDIS_ERROR, thread_id)
        return

    job = BuildJob(
        build_id=build_id, project=project, branch=branch,
        user_id=user_id, user_name=first_name,
        chat_id=chat_id, thread_id=thread_id,
        command_message_id=message_id,
    )

    placeholder_path = _create_placeholder(build_id, project, branch)
    job.message_id = _send_placeholder(chat_id, thread_id, placeholder_path, build_id, project, branch)

    success, _ = build_queue.put(job)
    if not success:
        if job.message_id:
            edit_message_media(chat_id, job.message_id, placeholder_path, messages.BUILD_QUEUE_FULL)
        else:
            _send(chat_id, messages.BUILD_QUEUE_FULL, thread_id)


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


def _parse_build_args(chat_id, thread_id, text):
    parts = text.strip().split()
    if len(parts) < 2:
        _send(chat_id, messages.BUILD_SYNTAX, thread_id)
        return None
    project = parts[1]
    branch = parts[2] if len(parts) > 2 else "main"
    return project, branch


def _validate_project_exists(chat_id, thread_id, project) -> bool:
    if validate_project(project):
        _send(chat_id, messages.build_project_not_found(project), thread_id)
        return False
    return True


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
