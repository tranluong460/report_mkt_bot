import os
import subprocess
import time
from pathlib import Path
from datetime import datetime
from typing import Callable

from bot.config import BUILD_LOG_DIR, BUILD_PROJECT_DIR, VN_TZ


def ensure_log_dir():
    Path(BUILD_LOG_DIR).mkdir(parents=True, exist_ok=True)


# Build steps - {branch} sẽ được thay bằng branch thực tế
BUILD_STEPS = [
    ("git reset --hard", "Git reset"),
    ("git fetch --all --prune", "Git fetch"),
    ("git checkout {branch}", "Checkout {branch}"),
    ("git pull --all --prune", "Git pull"),
    ("yarn", "Yarn install"),
    ("yarn vitech", "Yarn vitech"),
    ("yarn build:win:zip", "Build Win Zip"),
]


def get_project_dir(project: str) -> str:
    """Trả về đường dẫn thư mục dự án trong BUILD_PROJECT_DIR."""
    return os.path.join(BUILD_PROJECT_DIR, project)


def validate_project(project: str) -> str | None:
    """Kiểm tra thư mục dự án có tồn tại không. Trả về lỗi nếu có."""
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
    """
    Chạy build từng bước trong thư mục D:/Code/<project>.

    on_step(current_step, total_steps, step_name, status) callback
    để cập nhật tiến độ realtime lên Telegram.

    Returns dict: success, duration, log_path, error, failed_step
    """
    ensure_log_dir()
    log_path = os.path.join(BUILD_LOG_DIR, f"build-{build_id}.log")
    start_time = time.time()
    project_dir = get_project_dir(project)

    steps = BUILD_STEPS
    total = len(steps)

    with open(log_path, "w", encoding="utf-8") as log_file:
        # Header
        log_file.write(f"{'=' * 50}\n")
        log_file.write(f"  Build #{build_id}\n")
        log_file.write(f"  Dự án: {project}\n")
        log_file.write(f"  Branch: {branch}\n")
        log_file.write(f"  Thư mục: {project_dir}\n")
        log_file.write(f"  Bắt đầu: {datetime.now(VN_TZ).strftime('%Y-%m-%d %H:%M:%S')}\n")
        log_file.write(f"  Số bước: {total}\n")
        log_file.write(f"{'=' * 50}\n\n")
        log_file.flush()

        for i, (cmd_template, label_template) in enumerate(steps, 1):
            cmd = cmd_template.format(branch=branch)
            label = label_template.format(branch=branch)
            step_start = time.time()

            # Thông báo tiến độ
            if on_step:
                on_step(i, total, label, "running")

            # Ghi log bước
            log_file.write(f"--- [{i}/{total}] {label} ---\n")
            log_file.write(f"$ {cmd}\n")
            log_file.flush()

            try:
                result = subprocess.run(
                    cmd,
                    shell=True,
                    stdout=log_file,
                    stderr=subprocess.STDOUT,
                    timeout=1800,
                    cwd=project_dir,
                )
                step_duration = time.time() - step_start

                if result.returncode != 0:
                    log_file.write(f"\n!!! THẤT BẠI (exit code {result.returncode}, {step_duration:.1f}s) !!!\n\n")
                    log_file.flush()

                    if on_step:
                        on_step(i, total, label, "failed")

                    duration = time.time() - start_time
                    return {
                        "success": False,
                        "duration": duration,
                        "log_path": log_path,
                        "error": f"Bước [{i}/{total}] {label} thất bại (exit code {result.returncode})",
                        "failed_step": i,
                    }

                log_file.write(f"--- OK ({step_duration:.1f}s) ---\n\n")
                log_file.flush()

                if on_step:
                    on_step(i, total, label, "done")

            except subprocess.TimeoutExpired:
                log_file.write(f"\n!!! TIMEOUT (30 phút) !!!\n\n")
                log_file.flush()

                if on_step:
                    on_step(i, total, label, "timeout")

                duration = time.time() - start_time
                return {
                    "success": False,
                    "duration": duration,
                    "log_path": log_path,
                    "error": f"Bước [{i}/{total}] {label} timeout (30 phút)",
                    "failed_step": i,
                }

            except Exception as e:
                log_file.write(f"\n!!! LỖI: {e} !!!\n\n")
                log_file.flush()

                if on_step:
                    on_step(i, total, label, "error")

                duration = time.time() - start_time
                return {
                    "success": False,
                    "duration": duration,
                    "log_path": log_path,
                    "error": f"Bước [{i}/{total}] {label}: {e}",
                    "failed_step": i,
                }

        # Hoàn thành
        duration = time.time() - start_time
        log_file.write(f"{'=' * 50}\n")
        log_file.write(f"  BUILD THÀNH CÔNG\n")
        log_file.write(f"  Thời gian: {_fmt_duration(duration)}\n")
        log_file.write(f"  Kết thúc: {datetime.now(VN_TZ).strftime('%Y-%m-%d %H:%M:%S')}\n")
        log_file.write(f"{'=' * 50}\n")

    return {
        "success": True,
        "duration": duration,
        "log_path": log_path,
        "error": None,
        "failed_step": None,
    }


def get_log_tail(log_path: str, lines: int = 30) -> str:
    """Đọc N dòng cuối của file log."""
    try:
        with open(log_path, "r", encoding="utf-8") as f:
            all_lines = f.readlines()
            tail = all_lines[-lines:]
            return "".join(tail)
    except FileNotFoundError:
        return "(không tìm thấy file log)"


def get_dist_files(project: str) -> dict:
    """Tìm file zip mới nhất và file latest.yml trong dist/ của dự án."""
    dist_dir = os.path.join(get_project_dir(project), "dist")
    result = {"zip": None, "latest": None}

    if not os.path.isdir(dist_dir):
        return result

    # Tìm file .zip mới nhất
    zip_files = [
        os.path.join(dist_dir, f)
        for f in os.listdir(dist_dir)
        if f.endswith(".zip")
    ]
    if zip_files:
        result["zip"] = max(zip_files, key=os.path.getmtime)

    # Tìm file latest (latest.yml, latest-mac.yml, latest-linux.yml, ...)
    latest_files = [
        os.path.join(dist_dir, f)
        for f in os.listdir(dist_dir)
        if f.startswith("latest") and os.path.isfile(os.path.join(dist_dir, f))
    ]
    if latest_files:
        result["latest"] = max(latest_files, key=os.path.getmtime)

    return result


def _fmt_duration(seconds: float) -> str:
    m = int(seconds // 60)
    s = int(seconds % 60)
    return f"{m}m{s}s" if m > 0 else f"{s}s"
