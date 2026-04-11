"""Startup tasks: cleanup orphan messages từ lần chạy trước."""

import logging

from bot import messages
from bot.core.store import get_all_active_builds, clear_active_builds
from bot.core.telegram import edit_message_caption

logger = logging.getLogger("bot.startup")


def cleanup_orphan_builds() -> None:
    """Khi bot khởi động, edit các placeholder message cũ thành 'bị gián đoạn'.

    Active builds được lưu vào Redis khi enqueue + khi worker nhận job.
    Unregister khi job hoàn thành. Nếu bot crash → còn sót lại trong Redis.
    """
    active = get_all_active_builds()
    if not active:
        return

    logger.info(f"Found {len(active)} orphan builds from previous run, cleaning up...")

    for build_id_str, info in active.items():
        try:
            build_id = int(build_id_str)
        except ValueError:
            continue

        chat_id = info.get("chat_id")
        project = info.get("project", "?")
        branch = info.get("branch", "?")
        build_msg_id = info.get("build_msg_id")
        log_msg_id = info.get("log_msg_id")

        msg = messages.build_interrupted(build_id, project, branch)

        # Edit message trong BUILD topic (placeholder)
        if chat_id and build_msg_id:
            edit_message_caption(int(chat_id), int(build_msg_id), msg)
            logger.info(f"  Cleaned up build #{build_id} in build topic")

        # Edit message trong LOG topic (nếu có)
        if chat_id and log_msg_id:
            edit_message_caption(int(chat_id), int(log_msg_id), msg)
            logger.info(f"  Cleaned up build #{build_id} in log topic")

    clear_active_builds()
    logger.info("Orphan cleanup done.")
