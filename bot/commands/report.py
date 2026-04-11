"""Report handler: parse và lưu báo cáo trong report topic."""

from bot.config import TOPIC_ID
from bot.constants import EMOJI_THUMBS_UP, EMOJI_THINKING
from bot.parser import parse_report
from bot.store import save_report
from bot.telegram import react_to_message, send_telegram_message
from bot import messages


def handle_report(chat_id, message_id, thread_id, text, user_id, first_name) -> bool:
    """Xử lý message trong report topic. Trả về True nếu đã handle."""
    if not thread_id or str(thread_id) != str(TOPIC_ID):
        return False
    if not text.strip():
        return False

    if text.strip().lower().startswith("date:"):
        report = parse_report(text)
        if report["date"] and report["name"] and report["projects"]:
            save_report(user_id, report)
            react_to_message(chat_id, message_id, EMOJI_THUMBS_UP)
        else:
            react_to_message(chat_id, message_id, EMOJI_THINKING)
            send_telegram_message(chat_id, messages.report_format_help(), thread_id)
    else:
        react_to_message(chat_id, message_id, EMOJI_THINKING)

    return True
