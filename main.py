"""Entry point - khởi động bot + scheduler + build worker."""

import logging
import signal
import sys
import threading

from apscheduler.schedulers.background import BackgroundScheduler

from bot.config import validate_config, GROUP_CHAT_ID, TOPIC_ID, WEEKLY_TOPIC_ID
from bot.core.store import db
from bot.constants import BOT_COMMANDS, SCHEDULE_JOBS, IDLE_CHECK_MINUTES
from bot.core.telegram import delete_webhook, send_html, set_my_commands
from bot import messages
from bot.runtime.startup import cleanup_orphan_builds
from bot.builder.queue import BuildQueue
from bot.builder.worker import BuildWorker
from bot.runtime.poller import run_polling


def setup_logging():
    from logging.handlers import RotatingFileHandler
    import os

    log_dir = os.environ.get("BOT_LOG_DIR", "logs")
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, "bot.log")

    fmt = logging.Formatter(
        "%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(fmt)

    # File handler - rotate khi file > 10MB, giữ 5 backup
    file_handler = RotatingFileHandler(
        log_file, maxBytes=10 * 1024 * 1024, backupCount=5, encoding="utf-8"
    )
    file_handler.setFormatter(fmt)

    logging.basicConfig(
        level=logging.INFO,
        handlers=[console_handler, file_handler],
        force=True,
    )
    sys.stdout.reconfigure(line_buffering=True)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("apscheduler").setLevel(logging.WARNING)


setup_logging()
logger = logging.getLogger("bot")
stop_event = threading.Event()


# ============ Scheduled tasks ============

def send_daily_reminder():
    logger.info("Sending daily reminder...")
    send_html(GROUP_CHAT_ID, messages.daily_reminder(), TOPIC_ID)


def send_weekly_reminder():
    logger.info("Sending weekly reminder...")
    send_html(GROUP_CHAT_ID, messages.weekly_reminder(), WEEKLY_TOPIC_ID)


def setup_scheduler() -> BackgroundScheduler:
    from bot.runtime.scheduled import send_daily_task_report, check_idle_users

    # Map label → handler function
    job_handlers = {
        "Báo cáo task hôm nay": send_daily_task_report,
        "Nhắc báo cáo ngày": send_daily_reminder,
        "Nhắc báo cáo tuần": send_weekly_reminder,
    }

    scheduler = BackgroundScheduler(timezone="UTC")
    for label, hour, minute, day_of_week in SCHEDULE_JOBS:
        handler = job_handlers[label]
        scheduler.add_job(handler, "cron", hour=hour, minute=minute,
                          day_of_week=day_of_week, misfire_grace_time=300)

    # Idle check mỗi N phút
    scheduler.add_job(check_idle_users, "interval", minutes=IDLE_CHECK_MINUTES,
                      misfire_grace_time=120, id="idle_check")
    return scheduler


def handle_shutdown(signum, frame):
    logger.info("Shutting down...")
    stop_event.set()


def main():
    logger.info("Validating config...")
    validate_config()
    logger.info("Config OK")

    # Test Redis
    if db:
        try:
            db.ping()
            logger.info("Redis connected")
        except Exception as e:
            logger.warning(f"Redis ping failed: {e}")
    else:
        logger.warning("Redis not configured")

    # Delete webhook (để long polling hoạt động)
    logger.info("Deleting webhook...")
    delete_webhook()

    # Đăng ký bot commands (hiện menu "/" trong Telegram)
    logger.info("Registering bot commands...")
    if set_my_commands(BOT_COMMANDS):
        logger.info(f"Registered {len(BOT_COMMANDS)} commands")
    else:
        logger.warning("Failed to register commands")

    # Cleanup orphan builds từ lần chạy trước (nếu bot crash)
    logger.info("Cleaning up orphan builds...")
    cleanup_orphan_builds()

    # Start scheduler
    scheduler = setup_scheduler()
    scheduler.start()
    logger.info(f"Scheduler started: {len(SCHEDULE_JOBS)} jobs")

    # Start build worker
    build_queue = BuildQueue()
    build_worker = BuildWorker(build_queue)
    build_worker.start()
    logger.info("Build worker started")

    # Signal handlers
    signal.signal(signal.SIGINT, handle_shutdown)
    signal.signal(signal.SIGTERM, handle_shutdown)

    logger.info("=" * 40)
    logger.info("Bot is running! Press Ctrl+C to stop.")
    logger.info("=" * 40)

    try:
        run_polling(build_queue, stop_event)
    except KeyboardInterrupt:
        pass
    finally:
        logger.info("Stopping scheduler...")
        scheduler.shutdown(wait=False)
        logger.info("Stopping build worker...")
        build_worker.stop()
        logger.info("Bot stopped.")


if __name__ == "__main__":
    main()
