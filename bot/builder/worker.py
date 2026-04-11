"""Build worker - chạy job từ queue, báo tiến độ về Telegram."""

import logging
import os
import threading
from datetime import datetime

from bot.config import VN_TZ, BUILD_TOPIC_ID, LOG_TOPIC_ID, GROUP_CHAT_ID, BUILD_LOG_DIR
from bot.constants import STEP_ICONS
from bot.telegram import (
    send_telegram_message, edit_message_caption, send_document,
    edit_message_media, delete_message,
)
from bot.store import save_build_record, get_today_reports
from bot.parser import get_project_done_items
from bot import messages
from bot.builder.queue import BuildQueue, BuildJob
from bot.builder.executor import execute_build, get_dist_files, ensure_log_dir, _fmt_duration

logger = logging.getLogger("bot.worker")


class BuildWorker:
    def __init__(self, build_queue: BuildQueue):
        self._queue = build_queue
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()

    def start(self):
        self._thread = threading.Thread(target=self._run, daemon=True, name="build-worker")
        self._thread.start()

    def stop(self):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=5)

    def _run(self):
        while not self._stop.is_set():
            job = self._queue.get(timeout=2.0)
            if job is None:
                continue
            try:
                self._process_job(job)
            except Exception as e:
                logger.exception(f"Build #{job.build_id} crashed")
                self._report_system_error(job, str(e))
            finally:
                self._queue.done()

    def _process_job(self, job: BuildJob):
        chat_id = int(GROUP_CHAT_ID)
        build_thread_id = int(BUILD_TOPIC_ID)
        log_thread_id = int(LOG_TOPIC_ID) if LOG_TOPIC_ID else build_thread_id

        # Gửi placeholder vào LOG topic
        log_msg_id = self._send_log_placeholder(chat_id, log_thread_id, job)

        # Callback cập nhật tiến độ
        step_status: list[tuple[str, str]] = []
        build_start = datetime.now(VN_TZ)

        def on_step(current: int, total: int, label: str, status: str):
            while len(step_status) < total:
                step_status.append(("", "pending"))
            step_status[current - 1] = (label, status)
            if log_msg_id:
                elapsed = _fmt_duration((datetime.now(VN_TZ) - build_start).total_seconds())
                msg = messages.build_log_header(
                    job.build_id, job.project, job.branch, job.user_name,
                    elapsed, step_status, total,
                )
                edit_message_caption(chat_id, log_msg_id, msg)

        # Chạy build
        result = execute_build(job.project, job.branch, job.build_id, on_step=on_step)
        duration_str = _fmt_duration(result["duration"])

        # Lưu Redis
        self._save_record(job, result, duration_str)

        # Cập nhật step status cuối
        self._finalize_step_status(step_status, result)

        # Cập nhật LOG topic
        self._update_log_topic(chat_id, log_msg_id, log_thread_id, job, result,
                               duration_str, step_status)

        # Cập nhật BUILD topic
        self._update_build_topic(chat_id, build_thread_id, job, result, duration_str)

        # Xoá message /build của user
        if job.command_message_id:
            delete_message(chat_id, job.command_message_id)

    # ===== Helpers =====

    def _send_log_placeholder(self, chat_id: int, thread_id: int, job: BuildJob) -> int | None:
        ensure_log_dir()
        log_path = os.path.join(BUILD_LOG_DIR, f"build-{job.build_id}.log")
        with open(log_path, "w", encoding="utf-8") as f:
            f.write(f"Build #{job.build_id} - {job.project} ({job.branch}) - đang chờ...\n")

        caption = messages.build_waiting(job.build_id, job.project, job.branch)
        result = send_document(chat_id, log_path, caption=caption, thread_id=thread_id, parse_mode="HTML")
        return result["result"]["message_id"] if result.get("ok") else None

    def _save_record(self, job: BuildJob, result: dict, duration_str: str):
        save_build_record({
            "id": job.build_id,
            "project": job.project,
            "branch": job.branch,
            "user_name": job.user_name,
            "success": result["success"],
            "duration": duration_str,
            "error": result["error"],
            "finished_at": datetime.now(VN_TZ).strftime("%d/%m %H:%M"),
        })

    def _finalize_step_status(self, step_status: list, result: dict):
        if result["success"]:
            for i in range(len(step_status)):
                step_status[i] = (step_status[i][0], "done")
        else:
            failed = result.get("failed_step", len(step_status))
            for i in range(len(step_status)):
                if i < failed - 1:
                    step_status[i] = (step_status[i][0], "done")

    def _update_log_topic(self, chat_id, log_msg_id, log_thread_id, job, result, duration_str, step_status):
        msg = messages.build_log_final(
            job.build_id, job.project, job.branch, job.user_name,
            duration_str, step_status, result["success"], result["error"],
        )
        if log_msg_id and result["log_path"]:
            edit_message_media(chat_id, log_msg_id, result["log_path"], msg)
        elif log_msg_id:
            edit_message_caption(chat_id, log_msg_id, msg)
        elif result["log_path"]:
            send_document(chat_id, result["log_path"], caption=msg,
                          thread_id=log_thread_id, parse_mode="HTML")
        else:
            send_telegram_message(chat_id, msg, log_thread_id, parse_mode="HTML")

    def _update_build_topic(self, chat_id, build_thread_id, job, result, duration_str):
        build_msg_id = job.message_id

        if result["success"]:
            self._handle_build_success(chat_id, build_thread_id, build_msg_id, job, result)
        else:
            self._handle_build_failure(chat_id, build_thread_id, build_msg_id, job, result, duration_str)

    def _handle_build_success(self, chat_id, build_thread_id, build_msg_id, job, result):
        dist = get_dist_files(job.project)
        logger.info(f"Build #{job.build_id} OK | zip={dist['zip']} | latest={dist['latest']}")

        # Caption: done items của project hôm nay
        reports = get_today_reports()
        done_items = get_project_done_items(reports, job.project)
        caption = messages.build_success_caption(job.project, done_items)

        # Edit placeholder → zip thật
        if build_msg_id and dist["zip"]:
            edit_message_media(chat_id, build_msg_id, dist["zip"], caption)
        elif build_msg_id:
            edit_message_caption(chat_id, build_msg_id, caption)
        else:
            send_telegram_message(chat_id, caption, build_thread_id, parse_mode="HTML")

        # Gửi latest.yml riêng
        if dist["latest"]:
            send_document(
                chat_id, dist["latest"],
                caption=f"Build #{job.build_id} - {os.path.basename(dist['latest'])}",
                thread_id=build_thread_id,
            )

    def _handle_build_failure(self, chat_id, build_thread_id, build_msg_id, job, result, duration_str):
        logger.info(f"Build #{job.build_id} FAILED: {result['error']}")

        caption = messages.build_failure_caption(
            job.build_id, job.project, job.branch, job.user_name,
            result["error"] or "Lỗi không xác định",
        )

        if build_msg_id and result["log_path"]:
            edit_message_media(chat_id, build_msg_id, result["log_path"], caption)
        elif build_msg_id:
            edit_message_caption(chat_id, build_msg_id, caption)
        else:
            send_telegram_message(chat_id, caption, build_thread_id, parse_mode="HTML")

    def _report_system_error(self, job: BuildJob, error: str):
        chat_id = int(GROUP_CHAT_ID)
        thread_id = int(LOG_TOPIC_ID) if LOG_TOPIC_ID else int(BUILD_TOPIC_ID)
        send_telegram_message(
            chat_id, messages.build_system_error(job.build_id, error),
            thread_id, parse_mode="HTML",
        )
