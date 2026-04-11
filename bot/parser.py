"""Parser báo cáo - chuyển text format thành dict."""

import re
from datetime import datetime

from bot.config import VN_TZ
from bot.constants import REPORT_SECTIONS, PROJECT_SECTIONS, GLOBAL_SECTIONS

_PROJECT_HEADER_RE = re.compile(r"^\[.+?\]\s+(.+)")


def _new_project(name: str) -> dict:
    return {"name": name, "done": [], "doing": [], "issue": []}


def _empty_report() -> dict:
    return {"date": None, "name": None, "projects": [], "support": [], "plan": []}


def _parse_key_value(line: str, key: str) -> str | None:
    """Nếu line bắt đầu bằng 'key:' thì trả về phần value, ngược lại None."""
    if line.lower().startswith(f"{key}:"):
        return line[len(key) + 1:].strip()
    return None


def _parse_project_header(line: str) -> str | None:
    """Trả về tên project nếu line là header [X] Name, ngược lại None."""
    m = _PROJECT_HEADER_RE.match(line)
    return m.group(1).strip() if m else None


def _parse_section_header(line: str) -> str | None:
    """Trả về tên section nếu line là header section, ngược lại None."""
    lower = line.lower().rstrip(":")
    return lower if lower in REPORT_SECTIONS else None


def _parse_item(line: str) -> str | None:
    """Trả về nội dung item nếu line là '- xxx', ngược lại None."""
    if not line.startswith("-"):
        return None
    item = line[1:].strip()
    return item or None


def parse_report(text: str) -> dict:
    """Parse text báo cáo thành dict.

    Format:
        date: YYYY-MM-DD
        name: Tên
        [A] Tên dự án
        Done:
        - item1
        Doing:
        - item2
        ...
    """
    result = _empty_report()
    current_project = None
    current_section = None

    for raw in text.split("\n"):
        line = raw.strip()
        if not line:
            continue

        # date: / name:
        date_val = _parse_key_value(line, "date")
        if date_val is not None:
            result["date"] = date_val
            continue
        name_val = _parse_key_value(line, "name")
        if name_val is not None:
            result["name"] = name_val
            continue

        # Project header
        project_name = _parse_project_header(line)
        if project_name is not None:
            current_project = _new_project(project_name)
            result["projects"].append(current_project)
            current_section = None
            continue

        # Section header
        section = _parse_section_header(line)
        if section is not None:
            current_section = section
            if section in GLOBAL_SECTIONS:
                current_project = None
            continue

        # Item "- xxx"
        item = _parse_item(line)
        if item is None:
            continue
        if current_section in PROJECT_SECTIONS and current_project is not None:
            current_project[current_section].append(item)
        elif current_section in GLOBAL_SECTIONS:
            result[current_section].append(item)

    return result


def get_project_done_items(reports: dict, project_name: str) -> list:
    """Lấy done items của 1 project từ tất cả reports hôm nay.

    Match rules (theo thứ tự ưu tiên):
    1. Exact match (ignore case)
    2. Project trong report bắt đầu bằng build project (vd: build "mkt-care" match report "mkt-care-2025")
    3. Build project bắt đầu bằng report project (vd: build "mkt-care-2025" match report "mkt-care")
    """
    target = project_name.lower().strip()
    items = []
    seen = set()
    for report in reports.values():
        for proj in report.get("projects", []):
            name = proj.get("name", "").lower().strip()
            if not name:
                continue
            if name == target or name.startswith(target) or target.startswith(name):
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
