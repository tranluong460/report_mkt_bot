import os
import threading
from datetime import datetime
from html import escape

from bot.config import VN_TZ, BUILD_TOPIC_ID, LOG_TOPIC_ID, GROUP_CHAT_ID, BUILD_LOG_DIR
from bot.telegram import send_telegram_message, edit_message, send_document, send_media_group, edit_message_media, delete_message
from bot.store import save_build_record
from bot.builder.queue import BuildQueue, BuildJob
from bot.builder.executor import execute_build, get_dist_files, _fmt_duration


STEP_ICONS = {
    "running": "\u23f3",
    "done": "\u2705",
    "failed": "\u274c",
    "timeout": "\u23f0",
    "error": "\u26a0\ufe0f",
    "pending": "\u2b1c",
}


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
                self._report_error(job, str(e))
            finally:
                self._queue.done()

    def _get_log_topic_id(self):
        if LOG_TOPIC_ID:
            return int(LOG_TOPIC_ID)
        if BUILD_TOPIC_ID:
            return int(BUILD_TOPIC_ID)
        return None

    def _process_job(self, job: BuildJob):
        import logging
        logger = logging.getLogger("bot.worker")
        logger.info(f"Processing job #{job.build_id}, build_msg_id={job.message_id}")

        chat_id = int(GROUP_CHAT_ID)
        build_thread_id = int(BUILD_TOPIC_ID) if BUILD_TOPIC_ID else job.thread_id
        log_thread_id = self._get_log_topic_id()

        step_status: list[tuple[str, str]] = []
        log_msg_id = None
        build_start = datetime.now(VN_TZ)

        # Gửi document placeholder vào LOG topic
        log_path = os.path.join(BUILD_LOG_DIR, f"build-{job.build_id}.log")
        init_caption = (
            f"\U0001f528 <b>Build #{job.build_id}</b> đang chờ...\n"
            f"Dự án: <code>{escape(job.project)}</code> | Branch: <code>{escape(job.branch)}</code>"
        )
        if os.path.exists(log_path):
            init_result = send_document(chat_id, log_path, caption=init_caption, thread_id=log_thread_id, parse_mode="HTML")
            if init_result.get("ok"):
                log_msg_id = init_result["result"]["message_id"]

        def on_step(current: int, total: int, label: str, status: str):
            nonlocal step_status, log_msg_id

            while len(step_status) < total:
                step_status.append(("", "pending"))
            step_status[current - 1] = (label, status)

            msg = self._build_progress_msg(job, step_status, current, total, build_start)

            # Edit caption của document message trong LOG topic
            if log_msg_id:
                edit_message(chat_id, log_msg_id, msg, parse_mode="HTML")
            else:
                result = send_telegram_message(chat_id, msg, log_thread_id, parse_mode="HTML")
                if result.get("ok"):
                    log_msg_id = result["result"]["message_id"]

        # Chạy build
        build_result = execute_build(
            job.project, job.branch, job.build_id,
            on_step=on_step,
        )

        duration_str = _fmt_duration(build_result["duration"])

        # Lưu Redis
        save_build_record(job.build_id, {
            "pj": job.project,
            "b": job.branch,
            "u": job.user_name,
            "ok": build_result["success"],
            "d": duration_str,
            "e": build_result["error"],
            "t": datetime.now(VN_TZ).strftime("%m/%d %H:%M"),
        })

        # Tin nhắn kết quả chi tiết → LOG topic
        if build_result["success"]:
            for i in range(len(step_status)):
                step_status[i] = (step_status[i][0], "done")
            msg = self._build_final_msg(job, step_status, duration_str, success=True)
        else:
            failed = build_result.get("failed_step", len(step_status))
            for i in range(len(step_status)):
                if i < failed - 1:
                    step_status[i] = (step_status[i][0], "done")
            msg = self._build_final_msg(
                job, step_status, duration_str,
                success=False,
                error=build_result["error"],
            )

        # === LOG TOPIC: luôn thay bằng file log mới nhất ===
        if log_msg_id and build_result["log_path"]:
            edit_message_media(chat_id, log_msg_id, build_result["log_path"], msg)
        elif log_msg_id:
            edit_message(chat_id, log_msg_id, msg, parse_mode="HTML")
        else:
            if build_result["log_path"]:
                send_document(chat_id, build_result["log_path"], caption=msg, thread_id=log_thread_id, parse_mode="HTML")
            else:
                send_telegram_message(chat_id, msg, log_thread_id, parse_mode="HTML")

        # === BUILD TOPIC (media group: msg1=zip, msg2=yml) ===
        msg_zip = job.message_id      # message_id của file zip
        msg_yml = job.message_id_2    # message_id của file yml
        logger.info(f"Build #{job.build_id} done, msg_zip={msg_zip}, msg_yml={msg_yml}, success={build_result['success']}")

        if build_result["success"]:
            dist = get_dist_files(job.project)
            zip_name = os.path.basename(dist["zip"]) if dist["zip"] else ""
            zip_size = ""
            if dist["zip"]:
                size_mb = os.path.getsize(dist["zip"]) / (1024 * 1024)
                zip_size = f" ({size_mb:.1f} MB)"

            caption = (
                f"\u2705 <b>Build #{job.build_id} THÀNH CÔNG</b>\n"
                f"Dự án: <code>{escape(job.project)}</code> | Branch: <code>{escape(job.branch)}</code>\n"
                f"Bởi: {escape(job.user_name)} | Thời gian: <b>{duration_str}</b>"
            )
            if zip_name:
                caption += f"\nFile: <code>{escape(zip_name)}</code>{zip_size}"

            # Thành công → thay placeholder zip bằng zip thật
            if msg_zip and dist["zip"]:
                edit_message_media(chat_id, msg_zip, dist["zip"], caption)
            elif msg_zip:
                edit_message(chat_id, msg_zip, caption, parse_mode="HTML")

            # Thay placeholder yml bằng latest.yml thật
            if msg_yml and dist["latest"]:
                edit_message_media(chat_id, msg_yml, dist["latest"])
            elif msg_yml and not dist["latest"]:
                delete_message(chat_id, msg_yml)

        else:
            err = escape(build_result["error"] or "Lỗi không xác định")
            caption = (
                f"\u274c <b>Build #{job.build_id} THẤT BẠI</b>\n"
                f"Dự án: <code>{escape(job.project)}</code> | Branch: <code>{escape(job.branch)}</code>\n"
                f"Bởi: {escape(job.user_name)} | Lỗi: {err}"
            )

            # Thất bại → thay placeholder zip bằng file log
            if msg_zip and build_result["log_path"]:
                edit_message_media(chat_id, msg_zip, build_result["log_path"], caption)
            elif msg_zip:
                edit_message(chat_id, msg_zip, caption, parse_mode="HTML")

            # Xoá placeholder yml (không cần nữa)
            if msg_yml:
                delete_message(chat_id, msg_yml)


    def _build_progress_msg(self, job, step_status, current, total, start_time):
        elapsed = (datetime.now(VN_TZ) - start_time).total_seconds()

        lines = [
            f"\U0001f528 <b>Build #{job.build_id}</b> đang chạy...",
            f"Dự án: <code>{escape(job.project)}</code> | Branch: <code>{escape(job.branch)}</code>",
            f"Bởi: {escape(job.user_name)} | Đã chạy: {_fmt_duration(elapsed)}",
            "",
        ]

        for i, (label, status) in enumerate(step_status, 1):
            if not label:
                continue
            icon = STEP_ICONS.get(status, "\u2b1c")
            suffix = " &lt;--" if status == "running" else ""
            lines.append(f"  {icon} [{i}/{total}] {escape(label)}{suffix}")

        return "\n".join(lines)

    def _build_final_msg(self, job, step_status, duration_str, success, error=None):
        if success:
            lines = [
                f"\u2705 <b>Build #{job.build_id} THÀNH CÔNG</b>",
                f"Dự án: <code>{escape(job.project)}</code> | Branch: <code>{escape(job.branch)}</code>",
                f"Bởi: {escape(job.user_name)} | Thời gian: <b>{duration_str}</b>",
                "",
            ]
        else:
            lines = [
                f"\u274c <b>Build #{job.build_id} THẤT BẠI</b>",
                f"Dự án: <code>{escape(job.project)}</code> | Branch: <code>{escape(job.branch)}</code>",
                f"Bởi: {escape(job.user_name)} | Thời gian: <b>{duration_str}</b>",
                "",
            ]

        for i, (label, status) in enumerate(step_status, 1):
            if not label:
                continue
            icon = STEP_ICONS.get(status, "\u2b1c")
            lines.append(f"  {icon} [{i}/{len(step_status)}] {escape(label)}")

        if not success and error:
            lines.append(f"\n<b>Lỗi:</b> {escape(error)}")

        return "\n".join(lines)

    def _report_error(self, job: BuildJob, error: str):
        chat_id = int(GROUP_CHAT_ID)
        log_thread_id = self._get_log_topic_id()
        send_telegram_message(
            chat_id,
            f"\u26a0\ufe0f <b>Build #{job.build_id} LỖI HỆ THỐNG:</b> {escape(error)}",
            log_thread_id,
            parse_mode="HTML",
        )
