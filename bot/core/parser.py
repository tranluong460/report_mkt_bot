"""Parser báo cáo - chuyển text format thành dict."""

import re
from datetime import datetime

from bot.config import VN_TZ
from bot.constants import REPORT_SECTIONS, PROJECT_SECTIONS, GLOBAL_SECTIONS, DATE_FORMAT_DISPLAY

_PROJECT_HEADER_RE = re.compile(r"^\[.+?\]\s+(.+)")


def _new_project(name: str) -> dict:
    """Tạo dict project mới với các section từ PROJECT_SECTIONS."""
    return {"name": name, **{section: [] for section in PROJECT_SECTIONS}}


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


def project_report_names_match(build_project: str, report_project_name: str) -> bool:
    """Khớp tên dự án build với khối [X] trong báo cáo (cùng quy tắc với get_project_done_items).

    1. Trùng hoàn toàn (không phân biệt hoa thường)
    2. Tên trong report bắt đầu bằng slug build (vd: build "mkt-care" ↔ report "mkt-care-2025")
    3. Slug build bắt đầu bằng tên trong report
    """
    target = build_project.lower().strip()
    name = report_project_name.lower().strip()
    if not name or not target:
        return False
    return name == target or name.startswith(target) or target.startswith(name)


def get_project_done_items(reports: dict, project_name: str) -> list:
    """Lấy done items của 1 project từ tất cả reports hôm nay."""
    items = []
    seen = set()
    for report in reports.values():
        for proj in report.get("projects", []):
            if not project_report_names_match(project_name, proj.get("name", "")):
                continue
            for done in proj.get("done", []):
                if done and done not in seen:
                    seen.add(done)
                    items.append(done)
    return items


def has_today_report_for_project(reports: dict, project_name: str) -> bool:
    """True nếu hôm nay có ít nhất một báo cáo chứa khối dự án khớp với project_name (bất kỳ user)."""
    for report in reports.values():
        for proj in report.get("projects", []):
            if project_report_names_match(project_name, proj.get("name", "")):
                return True
    return False


def build_summary_message(reports: dict) -> str:
    """Gộp done items theo project, format tổng hợp ngày (HTML parse_mode)."""
    from bot import messages
    from html import escape

    if not reports:
        return messages.NO_REPORTS_TODAY

    projects: dict[str, list] = {}
    for report in reports.values():
        for proj in report.get("projects", []):
            name = proj["name"]
            done_items = [d for d in proj.get("done", []) if d]
            if done_items:
                projects.setdefault(name, []).extend(done_items)

    if not projects:
        return messages.NO_DONE_TODAY

    today = datetime.now(VN_TZ).strftime(DATE_FORMAT_DISPLAY)
    parts = [f"📋 <b>Tổng hợp done {today}</b>\n"]
    for project_name, done_items in projects.items():
        parts.append(f"<b>{escape(project_name)}</b>")
        for i, item in enumerate(done_items, 1):
            parts.append(f"{i}. {escape(item)}")
        parts.append("")

    return "\n".join(parts).strip()
