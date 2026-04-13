"""Export commands: /export - xuất báo cáo hôm nay ra file."""

import os
import tempfile
from datetime import datetime

from bot.config import VN_TZ
from bot.constants import DATE_FORMAT_KEY
from bot.core.store import get_today_reports
from bot.core.telegram import send_telegram_message, send_document
from bot import messages


def handle_export(chat_id, thread_id):
    """Export báo cáo hôm nay ra file text."""
    reports = get_today_reports()
    if not reports:
        send_telegram_message(chat_id, messages.NO_REPORTS_TODAY, thread_id)
        return

    today = datetime.now(VN_TZ).strftime(DATE_FORMAT_KEY)
    content = _format_reports_text(reports, today)

    # Ghi ra file tạm
    fd, path = tempfile.mkstemp(
        prefix=f"reports-{today}-", suffix=".txt", text=True,
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)

        send_document(
            chat_id, path,
            caption=f"Báo cáo ngày {today} ({len(reports)} người)",
            thread_id=thread_id,
        )
    finally:
        try:
            os.remove(path)
        except OSError:
            pass


def _format_reports_text(reports: dict, today: str) -> str:
    """Format reports thành text đọc được."""
    lines = [
        f"{'=' * 60}",
        f"  BÁO CÁO NGÀY {today}",
        f"  Tổng: {len(reports)} người",
        f"{'=' * 60}",
        "",
    ]

    for uid, report in reports.items():
        name = report.get("name", uid)
        lines.append(f"--- {name} ---")

        for proj in report.get("projects", []):
            pname = proj.get("name", "?")
            lines.append(f"\n[{pname}]")

            done = proj.get("done", [])
            if done:
                lines.append("Done:")
                for item in done:
                    lines.append(f"  - {item}")

            doing = proj.get("doing", [])
            if doing:
                lines.append("Doing:")
                for item in doing:
                    lines.append(f"  - {item}")

            issue = proj.get("issue", [])
            if issue:
                lines.append("Issue:")
                for item in issue:
                    lines.append(f"  - {item}")

        support = report.get("support", [])
        if support:
            lines.append("\nSupport:")
            for item in support:
                lines.append(f"  - {item}")

        plan = report.get("plan", [])
        if plan:
            lines.append("\nPlan:")
            for item in plan:
                lines.append(f"  - {item}")

        lines.append("")
        lines.append("")

    return "\n".join(lines)
