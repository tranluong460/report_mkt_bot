"""Build executor - chạy subprocess cho từng bước build."""

import logging
import os
import subprocess
import time
from datetime import datetime
from pathlib import Path
from typing import Callable

from bot.config import BUILD_LOG_DIR, BUILD_PROJECT_DIR, VN_TZ
from bot.constants import BUILD_STEPS, BUILD_TIMEOUT

logger = logging.getLogger("bot.executor")


def ensure_log_dir():
    Path(BUILD_LOG_DIR).mkdir(parents=True, exist_ok=True)


def get_project_dir(project: str) -> str:
    return os.path.join(BUILD_PROJECT_DIR, project)


def validate_project(project: str) -> str | None:
    """Trả về lỗi nếu project dir không tồn tại, None nếu OK."""
    project_dir = get_project_dir(project)
    if not os.path.isdir(project_dir):
        return f"Không tìm thấy thư mục: {project_dir}"
    return None


def execute_build(
    project: str,
    branch: str,
    build_id: int,
    on_step: Callable[[int, int, str, str], None] | None = None,
) -> dict:
    """Chạy build từng bước. Trả về dict: success, duration, log_path, error, failed_step."""
    ensure_log_dir()
    log_path = os.path.join(BUILD_LOG_DIR, f"build-{build_id}.log")
    project_dir = get_project_dir(project)
    start_time = time.time()
    total = len(BUILD_STEPS)

    with open(log_path, "w", encoding="utf-8") as log_file:
        _write_header(log_file, build_id, project, branch, project_dir, total)

        for i, (cmd_template, label_template) in enumerate(BUILD_STEPS, 1):
            cmd = cmd_template.format(branch=branch)
            label = label_template.format(branch=branch)

            if on_step:
                on_step(i, total, label, "running")

            result = _run_step(log_file, cmd, i, total, label, project_dir)

            if result["status"] != "done":
                if on_step:
                    on_step(i, total, label, result["status"])
                return {
                    "success": False,
                    "duration": time.time() - start_time,
                    "log_path": log_path,
                    "error": result["error"],
                    "failed_step": i,
                }

            if on_step:
                on_step(i, total, label, "done")

        duration = time.time() - start_time
        _write_footer(log_file, duration)

    return {
        "success": True,
        "duration": duration,
        "log_path": log_path,
        "error": None,
        "failed_step": None,
    }


def _write_header(log_file, build_id, project, branch, project_dir, total):
    log_file.write(f"{'=' * 50}\n")
    log_file.write(f"  Build #{build_id}\n")
    log_file.write(f"  Dự án: {project}\n")
    log_file.write(f"  Branch: {branch}\n")
    log_file.write(f"  Thư mục: {project_dir}\n")
    log_file.write(f"  Bắt đầu: {datetime.now(VN_TZ).strftime('%Y-%m-%d %H:%M:%S')}\n")
    log_file.write(f"  Số bước: {total}\n")
    log_file.write(f"{'=' * 50}\n\n")
    log_file.flush()


def _write_footer(log_file, duration):
    log_file.write(f"{'=' * 50}\n")
    log_file.write(f"  BUILD THÀNH CÔNG\n")
    log_file.write(f"  Thời gian: {_fmt_duration(duration)}\n")
    log_file.write(f"  Kết thúc: {datetime.now(VN_TZ).strftime('%Y-%m-%d %H:%M:%S')}\n")
    log_file.write(f"{'=' * 50}\n")


def _run_step(log_file, cmd, i, total, label, project_dir) -> dict:
    """Chạy 1 bước. Trả về dict: status (done/failed/timeout/error), error."""
    step_start = time.time()
    log_file.write(f"--- [{i}/{total}] {label} ---\n$ {cmd}\n")
    log_file.flush()

    try:
        result = subprocess.run(
            cmd, shell=True,
            stdout=log_file, stderr=subprocess.STDOUT,
            timeout=BUILD_TIMEOUT, cwd=project_dir,
        )
        dur = time.time() - step_start

        if result.returncode != 0:
            log_file.write(f"\n!!! THẤT BẠI (exit code {result.returncode}, {dur:.1f}s) !!!\n\n")
            log_file.flush()
            return {
                "status": "failed",
                "error": f"Bước [{i}/{total}] {label} thất bại (exit code {result.returncode})",
            }

        log_file.write(f"--- OK ({dur:.1f}s) ---\n\n")
        log_file.flush()
        return {"status": "done", "error": None}

    except subprocess.TimeoutExpired:
        log_file.write(f"\n!!! TIMEOUT (30 phút) !!!\n\n")
        log_file.flush()
        return {"status": "timeout", "error": f"Bước [{i}/{total}] {label} timeout (30 phút)"}

    except Exception as e:
        log_file.write(f"\n!!! LỖI: {e} !!!\n\n")
        log_file.flush()
        return {"status": "error", "error": f"Bước [{i}/{total}] {label}: {e}"}


# ============ DIST FILES ============

def get_dist_files(project: str) -> dict:
    """Tìm file zip mới nhất và file latest.* trong dist/."""
    dist_dir = os.path.join(get_project_dir(project), "dist")
    result = {"zip": None, "latest": None}
    if not os.path.isdir(dist_dir):
        return result

    zips = _find_files_by_ext(dist_dir, ".zip")
    if zips:
        result["zip"] = max(zips, key=os.path.getmtime)

    latests = [
        os.path.join(dist_dir, f)
        for f in os.listdir(dist_dir)
        if f.startswith("latest") and os.path.isfile(os.path.join(dist_dir, f))
    ]
    if latests:
        result["latest"] = max(latests, key=os.path.getmtime)

    return result


def _find_files_by_ext(directory: str, ext: str) -> list:
    return [
        os.path.join(directory, f)
        for f in os.listdir(directory)
        if f.endswith(ext)
    ]


# ============ LOG UTILS ============

def get_log_tail(log_path: str, lines: int = 30) -> str:
    try:
        with open(log_path, "r", encoding="utf-8") as f:
            return "".join(f.readlines()[-lines:])
    except FileNotFoundError:
        return "(không tìm thấy file log)"


def _fmt_duration(seconds: float) -> str:
    m = int(seconds // 60)
    s = int(seconds % 60)
    return f"{m}m{s}s" if m > 0 else f"{s}s"
