import logging
import signal
import threading

from apscheduler.schedulers.background import BackgroundScheduler

from bot.config import validate_config, GROUP_CHAT_ID, TOPIC_ID, WEEKLY_TOPIC_ID, BUILD_TOPIC_ID, VN_TZ
from bot.store import db
from bot.telegram import delete_webhook, send_telegram_message, get_report_message, get_weekly_report_message
from bot.parser import build_summary_message
from bot.store import get_today_reports
from bot.builder.queue import BuildQueue
from bot.builder.worker import BuildWorker
from bot.poller import run_polling

import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    stream=sys.stdout,
    force=True,
)
sys.stdout.reconfigure(line_buffering=True)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("apscheduler").setLevel(logging.WARNING)
logger = logging.getLogger("bot")

stop_event = threading.Event()


# --- Scheduled tasks (replace Vercel cron) ---

def send_daily_reminder():
    """Send daily report reminder. Runs at 16:00 VN (9:00 UTC)."""
    logger.info("Sending daily reminder...")
    send_telegram_message(
        int(GROUP_CHAT_ID),
        get_report_message(),
        int(TOPIC_ID),
    )


def send_weekly_reminder():
    """Send weekly report reminder. Runs at 16:00 VN Saturday (9:00 UTC)."""
    logger.info("Sending weekly reminder...")
    send_telegram_message(
        int(GROUP_CHAT_ID),
        get_weekly_report_message(),
        int(WEEKLY_TOPIC_ID),
    )


def send_daily_summary():
    """Send daily summary. Runs at 23:00 VN Mon-Sat (16:00 UTC)."""
    logger.info("Sending daily summary...")
    reports = get_today_reports()
    msg = build_summary_message(reports)
    send_telegram_message(
        int(GROUP_CHAT_ID),
        msg,
        int(BUILD_TOPIC_ID),
    )


def main():
    # 1. Validate config
    logger.info("Validating config...")
    validate_config()
    logger.info("Config OK")

    # 2. Test Redis
    if db:
        try:
            db.ping()
            logger.info("Redis connected")
        except Exception as e:
            logger.warning(f"Redis ping failed: {e}")
    else:
        logger.warning("Redis not configured (KV_REDIS_URL missing)")

    # 3. Delete webhook (required for getUpdates to work)
    logger.info("Deleting webhook...")
    if delete_webhook():
        logger.info("Webhook deleted")
    else:
        logger.warning("Failed to delete webhook (may not have been set)")

    # 4. Start scheduler (UTC)
    scheduler = BackgroundScheduler(timezone="UTC")
    # Daily reminder: 16:30 VN (09:30 UTC) T2-T6
    scheduler.add_job(send_daily_reminder, "cron", hour=9, minute=30, day_of_week="mon-fri")
    # Daily reminder: 11:00 VN (04:00 UTC) T7
    scheduler.add_job(send_daily_reminder, "cron", hour=4, minute=0, day_of_week="sat")
    # Weekly reminder: 09:00 VN (02:00 UTC) T7
    scheduler.add_job(send_weekly_reminder, "cron", hour=2, minute=0, day_of_week="sat")
    # Daily summary: 23:00 VN (16:00 UTC) T2-T7
    scheduler.add_job(send_daily_summary, "cron", hour=16, minute=0, day_of_week="mon-sat")
    scheduler.start()
    logger.info("Scheduler: daily 16:30 VN (T2-T6) / 11:00 VN (T7), weekly 09:00 VN (T7), summary 23:00 VN (T2-T7)")

    # 5. Start build worker
    build_queue = BuildQueue()
    build_worker = BuildWorker(build_queue)
    build_worker.start()
    logger.info("Build worker started")

    # 6. Handle shutdown signals
    def shutdown(signum, frame):
        logger.info("Shutting down...")
        stop_event.set()

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    # 7. Start polling (blocking)
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
