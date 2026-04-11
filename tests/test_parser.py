"""Unit tests cho bot/parser.py."""

import os
import sys
import unittest

# Mock env vars để import config không crash
for k in ['BOT_TOKEN', 'GROUP_CHAT_ID', 'TOPIC_ID', 'WEEKLY_TOPIC_ID',
          'BUILD_TOPIC_ID', 'LOG_TOPIC_ID', 'ADMIN_USER_ID',
          'KV_REDIS_URL', 'BUILD_LOG_DIR', 'BUILD_PROJECT_DIR']:
    os.environ.setdefault(k, 'test')

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from bot.parser import parse_report, get_project_done_items, build_summary_message


class TestParseReport(unittest.TestCase):

    def test_basic_single_project(self):
        text = """date: 11/04/2026
name: Lương
[A] mkt-care-2025
Done:
- Fix bug login
- Update UI
Doing:
- Task X
Issue:
- Bug abc"""
        r = parse_report(text)
        self.assertEqual(r["date"], "11/04/2026")
        self.assertEqual(r["name"], "Lương")
        self.assertEqual(len(r["projects"]), 1)
        p = r["projects"][0]
        self.assertEqual(p["name"], "mkt-care-2025")
        self.assertEqual(p["done"], ["Fix bug login", "Update UI"])
        self.assertEqual(p["doing"], ["Task X"])
        self.assertEqual(p["issue"], ["Bug abc"])

    def test_multiple_projects(self):
        text = """date: 11/04/2026
name: An
[A] project-1
Done:
- task A
[B] project-2
Done:
- task B"""
        r = parse_report(text)
        self.assertEqual(len(r["projects"]), 2)
        self.assertEqual(r["projects"][0]["name"], "project-1")
        self.assertEqual(r["projects"][0]["done"], ["task A"])
        self.assertEqual(r["projects"][1]["name"], "project-2")
        self.assertEqual(r["projects"][1]["done"], ["task B"])

    def test_global_sections(self):
        text = """date: 11/04/2026
name: Lương
[A] project-1
Done:
- task A
Support:
- help someone
Plan:
- plan item"""
        r = parse_report(text)
        self.assertEqual(r["support"], ["help someone"])
        self.assertEqual(r["plan"], ["plan item"])

    def test_case_insensitive_sections(self):
        text = """date: 11/04/2026
name: Lương
[A] project-1
DONE:
- task A
doing:
- task B"""
        r = parse_report(text)
        self.assertEqual(r["projects"][0]["done"], ["task A"])
        self.assertEqual(r["projects"][0]["doing"], ["task B"])

    def test_empty_report(self):
        r = parse_report("")
        self.assertIsNone(r["date"])
        self.assertIsNone(r["name"])
        self.assertEqual(r["projects"], [])

    def test_missing_fields(self):
        text = "name: Lương"
        r = parse_report(text)
        self.assertIsNone(r["date"])
        self.assertEqual(r["name"], "Lương")

    def test_section_with_colon_variations(self):
        text = """date: 11/04/2026
name: Lương
[A] project-1
Done
- task A
Doing:
- task B"""
        r = parse_report(text)
        self.assertEqual(r["projects"][0]["done"], ["task A"])
        self.assertEqual(r["projects"][0]["doing"], ["task B"])

    def test_dash_item_with_space(self):
        text = """date: 11/04/2026
name: Lương
[A] project-1
Done:
-task with no space
- task with space"""
        r = parse_report(text)
        self.assertEqual(r["projects"][0]["done"], ["task with no space", "task with space"])

    def test_empty_item_ignored(self):
        text = """date: 11/04/2026
name: Lương
[A] project-1
Done:
-
- real task"""
        r = parse_report(text)
        self.assertEqual(r["projects"][0]["done"], ["real task"])


class TestGetProjectDoneItems(unittest.TestCase):

    def _reports(self, *project_items):
        """Tạo reports dict từ list of (project_name, done_items)."""
        return {
            "user1": {
                "projects": [
                    {"name": name, "done": items}
                    for name, items in project_items
                ]
            }
        }

    def test_exact_match(self):
        reports = self._reports(("mkt-care-2025", ["task A", "task B"]))
        items = get_project_done_items(reports, "mkt-care-2025")
        self.assertEqual(items, ["task A", "task B"])

    def test_case_insensitive(self):
        reports = self._reports(("MKT-Care-2025", ["task A"]))
        items = get_project_done_items(reports, "mkt-care-2025")
        self.assertEqual(items, ["task A"])

    def test_prefix_match_short_target(self):
        # Build "mkt-care" matches report "mkt-care-2025"
        reports = self._reports(("mkt-care-2025", ["task A"]))
        items = get_project_done_items(reports, "mkt-care")
        self.assertEqual(items, ["task A"])

    def test_prefix_match_short_name(self):
        # Build "mkt-care-2025" matches report "mkt-care"
        reports = self._reports(("mkt-care", ["task A"]))
        items = get_project_done_items(reports, "mkt-care-2025")
        self.assertEqual(items, ["task A"])

    def test_no_match(self):
        reports = self._reports(("mkt-care-2025", ["task A"]))
        items = get_project_done_items(reports, "completely-different")
        self.assertEqual(items, [])

    def test_dedupe(self):
        # Cùng 1 done item xuất hiện nhiều lần → chỉ lấy 1
        reports = {
            "u1": {"projects": [{"name": "mkt-care", "done": ["task A"]}]},
            "u2": {"projects": [{"name": "mkt-care", "done": ["task A", "task B"]}]},
        }
        items = get_project_done_items(reports, "mkt-care")
        self.assertEqual(set(items), {"task A", "task B"})
        self.assertEqual(len(items), 2)

    def test_empty_project_name_ignored(self):
        reports = self._reports(("", ["task A"]))
        items = get_project_done_items(reports, "mkt-care")
        self.assertEqual(items, [])


class TestBuildSummaryMessage(unittest.TestCase):

    def test_empty_reports(self):
        msg = build_summary_message({})
        self.assertIn("Chưa có báo cáo", msg)

    def test_no_done_items(self):
        reports = {
            "u1": {"projects": [{"name": "p1", "done": []}]}
        }
        msg = build_summary_message(reports)
        self.assertIn("Chưa có task done", msg)

    def test_summary_format(self):
        reports = {
            "u1": {"projects": [{"name": "project-1", "done": ["task A", "task B"]}]},
            "u2": {"projects": [{"name": "project-2", "done": ["task C"]}]},
        }
        msg = build_summary_message(reports)
        self.assertIn("project-1", msg)
        self.assertIn("project-2", msg)
        self.assertIn("task A", msg)
        self.assertIn("task C", msg)


if __name__ == "__main__":
    unittest.main()
