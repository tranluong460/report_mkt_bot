import os
import httpx
from flask import Flask, jsonify, request
from datetime import datetime

from bot.config import TELEGRAM_API, TOPIC_ID, BUILD_TOPIC_ID, CRON_SECRET, VN_TZ
from bot.store import db, kv_get, kv_set, get_today_reports, save_report
from bot.parser import parse_report, build_summary_message
from bot.telegram import send_telegram_message, react_to_message, get_report_message

app = Flask(__name__)


def _check_auth() -> bool:
    auth = request.headers.get("Authorization")
    return not CRON_SECRET or auth == f"Bearer {CRON_SECRET}"


# --- Routes ---

@app.route("/api/index", methods=["GET"])
def cron_handler():
    if not _check_auth():
        return jsonify({"error": "Unauthorized"}), 401

    result = send_telegram_message(
        int(os.environ.get("GROUP_CHAT_ID")),
        get_report_message(),
        int(TOPIC_ID),
    )
    return jsonify(result)


@app.route("/api/summary", methods=["GET"])
def summary_handler():
    """Aggregate today's reports and post to the build topic."""
    if not _check_auth():
        return jsonify({"error": "Unauthorized"}), 401

    reports = get_today_reports()
    msg = build_summary_message(reports)
    result = send_telegram_message(
        int(os.environ.get("GROUP_CHAT_ID")),
        msg,
        int(BUILD_TOPIC_ID),
    )
    return jsonify(result)


@app.route("/api/index", methods=["POST"])
def webhook_handler():
    data = request.get_json()
    message = data.get("message", {})
    text = message.get("text", "")
    chat_id = message.get("chat", {}).get("id")
    thread_id = message.get("message_thread_id")
    message_id = message.get("message_id")
    user = message.get("from", {})
    user_id = str(user.get("id", ""))
    first_name = user.get("first_name", "")
    username = user.get("username", "")

    # Auto-save report when a user posts to the report topic
    if thread_id and str(thread_id) == str(TOPIC_ID) and text.strip():
        if text.strip().lower().startswith("date:"):
            report = parse_report(text)
            if report["date"] and report["name"] and report["projects"]:
                report["reporter"] = first_name
                save_report(user_id, report)
                react_to_message(chat_id, message_id, "👍")
            else:
                react_to_message(chat_id, message_id, "🤔")
        else:
            react_to_message(chat_id, message_id, "🤔")

    # /debug - kiểm tra trạng thái Redis và báo cáo hôm nay
    if text.strip().startswith("/debug"):
        redis_ok = db is not None
        reports = get_today_reports() if redis_ok else {}
        today = datetime.now(VN_TZ).strftime("%Y-%m-%d")
        reporters = [r.get("reporter", uid) for uid, r in reports.items()]
        lines = [
            "*🔧 Debug Info*",
            f"Redis: {'✅ connected' if redis_ok else '❌ not connected (KV_REDIS_URL missing)'}",
            f"TOPIC\\_ID: `{TOPIC_ID}`",
            f"BUILD\\_TOPIC\\_ID: `{BUILD_TOPIC_ID}`",
            f"thread\\_id tin nhắn này: `{thread_id}`",
            f"Báo cáo ngày {today}: *{len(reports)}* người",
        ]
        if reporters:
            lines.append("Đã nộp: " + ", ".join(reporters))
        send_telegram_message(chat_id, "\n".join(lines), thread_id)
        return jsonify({"ok": True})

    # /unfollow - hủy đăng ký (check trước /follow)
    if text.strip().startswith("/unfollow"):
        members = kv_get()
        if user_id in members:
            del members[user_id]
            kv_set(members)
        send_telegram_message(
            chat_id,
            f"*{first_name}* đã hủy đăng ký thông báo.",
            thread_id,
        )
        return jsonify({"ok": True})

    # /follow - đăng ký nhận tag
    if text.strip().startswith("/follow"):
        members = kv_get()
        members[user_id] = {"first_name": first_name, "username": username}
        kv_set(members)
        send_telegram_message(
            chat_id,
            f"*{first_name}* đã đăng ký nhận thông báo!",
            thread_id,
        )
        return jsonify({"ok": True})

    # /all <nội dung> - gửi nội dung kèm tag tất cả người đã follow
    if text.strip().startswith("/all"):
        content = text.strip()[4:].strip()
        if not content:
            content = text.strip().replace("/all@report_mkt_bot", "").strip()
        members = kv_get()
        if not members:
            send_telegram_message(
                chat_id,
                "Chưa có ai đăng ký. Dùng /follow để đăng ký nhận tag.",
                thread_id,
            )
        else:
            mentions = "".join(
                f'<a href="tg://user?id={uid}">\u200b</a>'
                for uid in members
            )
            msg = f"{text.strip()}\n{mentions}"
            httpx.post(
                f"{TELEGRAM_API}/deleteMessage",
                json={"chat_id": chat_id, "message_id": message_id},
            )
            send_telegram_message(chat_id, msg, thread_id, parse_mode="HTML")
        return jsonify({"ok": True})

    return jsonify({"ok": True})
