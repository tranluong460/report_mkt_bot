"""Parser báo cáo - chuyển text format thành dict."""

import re
from datetime import datetime

from bot.config import VN_TZ
from bot.constants import REPORT_SECTIONS, PROJECT_SECTIONS, GLOBAL_SECTIONS


def parse_report(text: str) -> dict:
    """Parse text báo cáo thành dict. Format:

        date: YYYY-MM-DD
        name: Tên
        [A] Tên dự án
        Done:
        - item1
        Doing:
        - item2
        ...
    """
    result = {
        "date": None,
        "name": None,
        "projects": [],
        "support": [],
        "plan": [],
    }
    current_project = None
    current_section = None

    for raw in text.split("\n"):
        line = raw.strip()

        if line.lower().startswith("date:"):
            result["date"] = line[5:].strip()
            continue

        if line.lower().startswith("name:"):
            result["name"] = line[5:].strip()
            continue

        # Project header: [A] Tên dự án
        m = re.match(r"^\[.+?\]\s+(.+)", line)
        if m:
            current_project = {
                "name": m.group(1).strip(),
                "done": [], "doing": [], "issue": [],
            }
            result["projects"].append(current_project)
            current_section = None
            continue

        # Section header (case-insensitive, có thể có :)
        lower = line.lower().rstrip(":")
        if lower in REPORT_SECTIONS:
            current_section = lower
            if lower in GLOBAL_SECTIONS:
                current_project = None
            continue

        # Item "- xxx"
        if line.startswith("-"):
            item = line[1:].strip()
            if not item:
                continue
            if current_section in PROJECT_SECTIONS and current_project is not None:
                current_project[current_section].append(item)
            elif current_section in GLOBAL_SECTIONS:
                result[current_section].append(item)

    return result


def get_project_done_items(reports: dict, project_name: str) -> list:
    """Lấy done items của 1 project từ tất cả reports hôm nay.
    Match theo tên project (case-insensitive, substring 2 chiều)."""
    target = project_name.lower().strip()
    items = []
    seen = set()
    for report in reports.values():
        for proj in report.get("projects", []):
            name = proj.get("name", "").lower().strip()
            if target in name or name in target:
                for done in proj.get("done", []):
                    if done and done not in seen:
                        seen.add(done)
                        items.append(done)
    return items


def build_summary_message(reports: dict) -> str:
    """Gộp done items theo project, format tổng hợp ngày."""
    if not reports:
        return "Chưa có báo cáo nào hôm nay."

    projects: dict[str, list] = {}
    for report in reports.values():
        for proj in report.get("projects", []):
            name = proj["name"]
            done_items = [d for d in proj.get("done", []) if d]
            if done_items:
                projects.setdefault(name, []).extend(done_items)

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
