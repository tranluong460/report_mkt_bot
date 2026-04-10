from bot.config import TOPIC_ID
from bot.parser import parse_report
from bot.store import save_report
from bot.telegram import react_to_message, send_telegram_message


def handle_report(chat_id: int, message_id: int, thread_id, text: str, user_id: str, first_name: str) -> bool:
    """Handle report messages in the report topic. Returns True if handled."""
    if not thread_id or str(thread_id) != str(TOPIC_ID):
        return False

    if not text.strip():
        return False

    if text.strip().lower().startswith("date:"):
        report = parse_report(text)
        if report["date"] and report["name"] and report["projects"]:
            report["reporter"] = first_name
            save_report(user_id, report)
            react_to_message(chat_id, message_id, "\U0001f44d")
        else:
            react_to_message(chat_id, message_id, "\U0001f914")
            send_telegram_message(
                chat_id,
                "Sai format. Cần có: `date:`, `name:`, và ít nhất 1 project `[A] Tên dự án`",
                thread_id,
            )
    else:
        react_to_message(chat_id, message_id, "\U0001f914")

    return True
