"""Các task chạy theo schedule."""

import logging

from bot.config import GROUP_CHAT_ID, TOPIC_ID, GENERAL_TOPIC_ID, VITECH_WEB_URL
from bot.core.store import get_user_link_map, get_members
from bot.core.telegram import send_html
from bot.api.vitech import (
    fetch_all_tasks, tasks_updated_today, task_prefix, within_last_minutes,
)
from bot import messages

logger = logging.getLogger("bot.scheduled")


# ============ 17h: Báo cáo tự động theo task hôm nay ============

def send_daily_task_report():
    """Gửi báo cáo các task được cập nhật hôm nay vào Report topic, nhóm theo PREFIX."""
    try:
        tasks = tasks_updated_today(fetch_all_tasks())
    except Exception as e:
        logger.error(f"Daily task report fetch failed: {e}")
        return

    if not tasks:
        send_html(GROUP_CHAT_ID, messages.NO_TASKS_TODAY, TOPIC_ID)
        return

    grouped: dict[str, list] = {}
    for t in tasks:
        prefix = task_prefix(t.get("code", ""))
        if not prefix:
            continue
        grouped.setdefault(prefix, []).append(t)

    logger.info(f"Daily task report: {len(tasks)} tasks, {len(grouped)} groups")
    send_html(GROUP_CHAT_ID, messages.daily_task_report(grouped), TOPIC_ID)


# ============ Mỗi 10p: nhắc user không có task in_progress ============

def check_idle_users():
    """Mỗi 10p: với mỗi linked user, nếu không có task in_progress
    được cập nhật trong 10 phút qua → tag trong topic chung."""
    link_map = get_user_link_map()  # {vitech_id: tg_id}
    if not link_map:
        return

    try:
        all_tasks = fetch_all_tasks()
    except Exception as e:
        logger.error(f"Idle check fetch failed: {e}")
        return

    # Lọc task in_progress + updated trong 10p qua
    active = [
        t for t in all_tasks
        if t.get("status") == "in_progress"
        and within_last_minutes(t.get("updatedAt"), 10)
    ]
    active_assignees = {t.get("assigneeId") for t in active if t.get("assigneeId")}

    members = get_members()
    idle_count = 0
    for vitech_id, tg_id in link_map.items():
        if vitech_id in active_assignees:
            continue
        info = members.get(tg_id, {})
        first_name = info.get("first_name") or "User"
        msg = messages.idle_notify(tg_id, first_name, VITECH_WEB_URL)
        send_html(GROUP_CHAT_ID, msg, GENERAL_TOPIC_ID)
        idle_count += 1

    if idle_count:
        logger.info(f"Idle check: notified {idle_count}/{len(link_map)} users")
