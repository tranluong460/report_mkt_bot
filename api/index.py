import os
import re
import json
import httpx
import redis
from flask import Flask, jsonify, request
from datetime import datetime, timezone, timedelta

app = Flask(__name__)

BOT_TOKEN = os.environ.get("BOT_TOKEN")
GROUP_CHAT_ID = os.environ.get("GROUP_CHAT_ID")
TOPIC_ID = os.environ.get("TOPIC_ID")
BUILD_TOPIC_ID = os.environ.get("BUILD_TOPIC_ID", "258")

TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}"

KV_REDIS_URL = os.environ.get("KV_REDIS_URL")
db = redis.from_url(KV_REDIS_URL) if KV_REDIS_URL else None

VN_TZ = timezone(timedelta(hours=7))
KV_KEY = "members"
REPORT_KEY_PREFIX = "reports"


# --- Redis helpers ---

def kv_get():
    if not db:
        return {}
    data = db.get(KV_KEY)
    return json.loads(data) if data else {}


def kv_set(members):
    if db:
        db.set(KV_KEY, json.dumps(members))


def get_today_reports():
    if not db:
        return {}
    today = datetime.now(VN_TZ).strftime("%Y-%m-%d")
    key = f"{REPORT_KEY_PREFIX}:{today}"
    data = db.get(key)
    return json.loads(data) if data else {}


def save_report(user_id, report):
    if not db:
        return
    today = datetime.now(VN_TZ).strftime("%Y-%m-%d")
    key = f"{REPORT_KEY_PREFIX}:{today}"
    reports = get_today_reports()
    reports[user_id] = report
    db.set(key, json.dumps(reports), ex=172800)  # 2-day TTL


# --- Report parsing ---

def parse_report(text):
    """Parse a structured report message into a dict."""
    lines = text.split("\n")
    result = {
        "date": None,
        "name": None,
        "projects": [],
        "support": [],
        "plan": [],
    }
    current_project = None
    current_section = None  # 'done' | 'doing' | 'issue' | 'support' | 'plan'

    for raw in lines:
        line = raw.strip()

        if line.lower().startswith("date:"):
            result["date"] = line[5:].strip()
            continue

        if line.lower().startswith("name:"):
            result["name"] = line[5:].strip()
            continue

        # Project header: [A] Tên dự án  or  [B] Tên dự án
        m = re.match(r"^\[.+?\]\s+(.+)", line)
        if m:
            current_project = {
                "name": m.group(1).strip(),
                "done": [],
                "doing": [],
                "issue": [],
            }
            result["projects"].append(current_project)
            current_section = None
            continue

        # Section headers (case-insensitive, with or without colon)
        lower = line.lower().rstrip(":")
        if lower in ("done", "doing", "issue", "support", "plan"):
            current_section = lower
            if lower in ("support", "plan"):
                current_project = None
            continue

        # Handle both "- item" and "-item" and bare "-"
        if line.startswith("-"):
            item = line[1:].strip()
            if not item:
                continue
            if current_section == "done" and current_project is not None:
                current_project["done"].append(item)
            elif current_section == "doing" and current_project is not None:
                current_project["doing"].append(item)
            elif current_section == "issue" and current_project is not None:
                current_project["issue"].append(item)
            elif current_section == "support":
                result["support"].append(item)
            elif current_section == "plan":
                result["plan"].append(item)

    return result


def build_summary_message(reports):
    """Aggregate done items by project name across all user reports."""
    if not reports:
        return "Chưa có báo cáo nào hôm nay."

    # {project_name: [done_item, ...]}
    projects = {}
    for report in reports.values():
        for proj in report.get("projects", []):
            name = proj["name"]
            done_items = [d for d in proj.get("done", []) if d]
            if done_items:
                if name not in projects:
                    projects[name] = []
                projects[name].extend(done_items)

    if not projects:
        return "Chưa có task done nào hôm nay."

    today = datetime.now(VN_TZ).strftime("%d/%m/%Y")
    parts = [f"📋 *Tổng hợp done {today}*\n"]
    for project_name, done_items in projects.items():
        parts.append(f"*{project_name}*")
        for i, item in enumerate(done_items, 1):
            parts.append(f"{i}. {item}")
        parts.append("")

    return "\n".join(parts).strip()


# --- Telegram helpers ---

def send_telegram_message(chat_id, text, thread_id=None, parse_mode="Markdown"):
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": parse_mode,
    }
    if thread_id:
        payload["message_thread_id"] = thread_id

    response = httpx.post(f"{TELEGRAM_API}/sendMessage", json=payload)
    return response.json()


def get_report_message():
    today = datetime.now(VN_TZ).strftime("%d/%m/%Y")
    return (
        f"*\U0001F4CB Nhắc báo cáo ngày {today}*\n\n"
        "Mọi người gửi báo cáo công việc hôm nay vào topic này nhé!"
    )


# --- Routes ---

@app.route("/api/index", methods=["GET"])
def cron_handler():
    auth = request.headers.get("Authorization")
    cron_secret = os.environ.get("CRON_SECRET")

    if cron_secret and auth != f"Bearer {cron_secret}":
        return jsonify({"error": "Unauthorized"}), 401

    result = send_telegram_message(
        int(GROUP_CHAT_ID), get_report_message(), int(TOPIC_ID)
    )
    return jsonify(result)


@app.route("/api/summary", methods=["GET"])
def summary_handler():
    """Aggregate today's reports and post to the build topic."""
    auth = request.headers.get("Authorization")
    cron_secret = os.environ.get("CRON_SECRET")

    if cron_secret and auth != f"Bearer {cron_secret}":
        return jsonify({"error": "Unauthorized"}), 401

    reports = get_today_reports()
    msg = build_summary_message(reports)
    result = send_telegram_message(int(GROUP_CHAT_ID), msg, int(BUILD_TOPIC_ID))
    return jsonify(result)


@app.route("/api/index", methods=["POST"])
def webhook_handler():
    data = request.get_json()
    message = data.get("message", {})
    text = message.get("text", "")
    chat_id = message.get("chat", {}).get("id")
    thread_id = message.get("message_thread_id")
    user = message.get("from", {})
    user_id = str(user.get("id", ""))
    first_name = user.get("first_name", "")
    username = user.get("username", "")

    # Auto-save report when a user posts to the report topic
    if (
        thread_id
        and str(thread_id) == str(TOPIC_ID)
        and text.strip().lower().startswith("date:")
    ):
        report = parse_report(text)
        report["reporter"] = first_name
        save_report(user_id, report)

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
            original_text = text.strip()
            msg = f"{original_text}\n{mentions}"
            httpx.post(
                f"{TELEGRAM_API}/deleteMessage",
                json={"chat_id": chat_id, "message_id": message.get("message_id")},
            )
            send_telegram_message(
                chat_id,
                msg,
                thread_id,
                parse_mode="HTML",
            )
        return jsonify({"ok": True})

    return jsonify({"ok": True})
