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

        # Tạo placeholder log file + gửi vào LOG topic
        from bot.builder.executor import ensure_log_dir
        ensure_log_dir()
        log_path = os.path.join(BUILD_LOG_DIR, f"build-{job.build_id}.log")
        with open(log_path, "w", encoding="utf-8") as f:
            f.write(f"Build #{job.build_id} - {job.project} ({job.branch}) - đang chờ...\n")

        init_caption = (
            f"\U0001f528 <b>Build #{job.build_id}</b> đang chờ...\n"
            f"Dự án: <code>{escape(job.project)}</code> | Branch: <code>{escape(job.branch)}</code>"
        )
        logger.info(f"[LOG] #{job.build_id} sending placeholder doc to log topic, thread={log_thread_id}")
        init_result = send_document(chat_id, log_path, caption=init_caption, thread_id=log_thread_id, parse_mode="HTML")
        logger.info(f"[LOG] #{job.build_id} placeholder result: ok={init_result.get('ok')} msg_id={init_result.get('result',{}).get('message_id')}")
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
        logger.info(f"[LOG] #{job.build_id} updating log topic | log_msg_id={log_msg_id} | log_path={build_result.get('log_path')}")
        if log_msg_id and build_result["log_path"]:
            logger.info(f"[LOG] #{job.build_id} editMedia log_msg_id={log_msg_id} -> {build_result['log_path']}")
            r = edit_message_media(chat_id, log_msg_id, build_result["log_path"], msg)
            logger.info(f"[LOG] #{job.build_id} editMedia result: ok={r.get('ok')} {r.get('description','')}")
        elif log_msg_id:
            logger.info(f"[LOG] #{job.build_id} editText log_msg_id={log_msg_id}")
            edit_message(chat_id, log_msg_id, msg, parse_mode="HTML")
        else:
            if build_result["log_path"]:
                logger.info(f"[LOG] #{job.build_id} sendDocument new (no log_msg_id)")
                send_document(chat_id, build_result["log_path"], caption=msg, thread_id=log_thread_id, parse_mode="HTML")
            else:
                logger.info(f"[LOG] #{job.build_id} sendText new (no log_msg_id, no log)")
                send_telegram_message(chat_id, msg, log_thread_id, parse_mode="HTML")

        # === BUILD TOPIC (2 document riêng: msg_zip + msg_yml) ===
        msg_zip = job.message_id
        msg_yml = job.message_id_2
        logger.info(f"[BUILD] #{job.build_id} done | success={build_result['success']} | msg_zip={msg_zip} | msg_yml={msg_yml} | log={build_result.get('log_path')}")

        if build_result["success"]:
            dist = get_dist_files(job.project)
            logger.info(f"[BUILD] #{job.build_id} dist files: zip={dist['zip']} | latest={dist['latest']}")

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

            # Edit zip placeholder → zip thật
            if msg_zip and dist["zip"]:
                logger.info(f"[BUILD] #{job.build_id} editMedia msg_zip={msg_zip} -> {dist['zip']}")
                r = edit_message_media(chat_id, msg_zip, dist["zip"])
                logger.info(f"[BUILD] #{job.build_id} editMedia zip result: ok={r.get('ok')} {r.get('description','')}")

            # Edit yml placeholder → latest.yml thật + caption
            if msg_yml and dist["latest"]:
                logger.info(f"[BUILD] #{job.build_id} editMedia msg_yml={msg_yml} -> {dist['latest']} + caption")
                r = edit_message_media(chat_id, msg_yml, dist["latest"], caption)
                logger.info(f"[BUILD] #{job.build_id} editMedia yml result: ok={r.get('ok')} {r.get('description','')}")
            elif msg_yml:
                logger.info(f"[BUILD] #{job.build_id} no latest.yml, editText msg_yml={msg_yml}")
                edit_message(chat_id, msg_yml, caption, parse_mode="HTML")

        else:
            err = escape(build_result["error"] or "Lỗi không xác định")
            caption = (
                f"\u274c <b>Build #{job.build_id} THẤT BẠI</b>\n"
                f"Dự án: <code>{escape(job.project)}</code> | Branch: <code>{escape(job.branch)}</code>\n"
                f"Bởi: {escape(job.user_name)} | Lỗi: {err}"
            )

            # Xoá zip placeholder
            if msg_zip:
                logger.info(f"[BUILD] #{job.build_id} deleteMessage msg_zip={msg_zip}")
                delete_message(chat_id, msg_zip)

            # Edit yml placeholder → log file + caption lỗi
            if msg_yml and build_result["log_path"]:
                logger.info(f"[BUILD] #{job.build_id} editMedia msg_yml={msg_yml} -> {build_result['log_path']} + caption")
                r = edit_message_media(chat_id, msg_yml, build_result["log_path"], caption)
                logger.info(f"[BUILD] #{job.build_id} editMedia yml->log result: ok={r.get('ok')} {r.get('description','')}")
            elif msg_yml:
                logger.info(f"[BUILD] #{job.build_id} no log, editText msg_yml={msg_yml}")
                edit_message(chat_id, msg_yml, caption, parse_mode="HTML")


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
