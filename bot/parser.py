import re
from datetime import datetime

from bot.config import VN_TZ


def parse_report(text: str) -> dict:
    """Parse a structured report message into a dict."""
    lines = text.split("\n")
    result: dict = {
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


def build_summary_message(reports: dict) -> str:
    """Aggregate done items by project name across all user reports."""
    if not reports:
        return "Chưa có báo cáo nào hôm nay."

    projects: dict = {}
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
