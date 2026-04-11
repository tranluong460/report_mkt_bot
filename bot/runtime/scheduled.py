"""Các task chạy theo schedule."""

import logging

from bot.config import GROUP_CHAT_ID, TOPIC_ID
from bot.core.store import get_members, get_today_reports
from bot.core.telegram import send_html
from bot import messages

logger = logging.getLogger("bot.scheduled")


def send_missing_report_alert():
    """Tag những member chưa nộp báo cáo hôm nay vào report topic."""
    members = get_members()
    reports = get_today_reports()

    missing = {
        uid: info for uid, info in members.items()
        if uid not in reports
    }

    if not missing:
        logger.info("Missing report alert: all members reported")
        return

    logger.info(f"Missing report alert: {len(missing)} users")
    msg = messages.missing_report_alert(missing)
    send_html(GROUP_CHAT_ID, msg, TOPIC_ID)
