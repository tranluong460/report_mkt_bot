"""Entry point - khởi động bot + scheduler + build worker."""

import logging
import signal
import sys
import threading

from apscheduler.schedulers.background import BackgroundScheduler

from bot.config import validate_config, GROUP_CHAT_ID, TOPIC_ID, WEEKLY_TOPIC_ID, BUILD_TOPIC_ID
from bot.core.store import db, get_today_reports
from bot.constants import BOT_COMMANDS
from bot.core.telegram import delete_webhook, send_html, set_my_commands
from bot.core.parser import build_summary_message
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


def send_daily_summary():
    logger.info("Sending daily summary...")
    reports = get_today_reports()
    msg = build_summary_message(reports)
    send_html(GROUP_CHAT_ID, msg, BUILD_TOPIC_ID)


def setup_scheduler() -> BackgroundScheduler:
    from bot.runtime.scheduled import send_missing_report_alert
    scheduler = BackgroundScheduler(timezone="UTC")
    # Nhắc ngày: 16:00 VN T2-T6 (09:00 UTC)
    scheduler.add_job(send_daily_reminder, "cron", hour=9, minute=0, day_of_week="mon-fri", misfire_grace_time=300)
    # Nhắc ngày: 10:00 VN T7 (03:00 UTC)
    scheduler.add_job(send_daily_reminder, "cron", hour=3, minute=0, day_of_week="sat", misfire_grace_time=300)
    # Nhắc tuần: 09:00 VN T7 (02:00 UTC)
    scheduler.add_job(send_weekly_reminder, "cron", hour=2, minute=0, day_of_week="sat", misfire_grace_time=300)
    # Missing report alert: 21:00 VN T2-T6 (14:00 UTC)
    scheduler.add_job(send_missing_report_alert, "cron", hour=14, minute=0, day_of_week="mon-fri", misfire_grace_time=300)
    # Missing report alert: 11:00 VN T7 (04:00 UTC)
    scheduler.add_job(send_missing_report_alert, "cron", hour=4, minute=0, day_of_week="sat", misfire_grace_time=300)
    # Tổng hợp: 23:00 VN T2-T7 (16:00 UTC)
    scheduler.add_job(send_daily_summary, "cron", hour=16, minute=0, day_of_week="mon-sat", misfire_grace_time=300)
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
    logger.info("Scheduler: daily 16:00 VN (T2-T6) / 10:00 VN (T7), weekly 09:00 VN (T7), missing alert 21:00 VN (T2-T6) / 11:00 VN (T7), summary 23:00 VN (T2-T7)")

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
