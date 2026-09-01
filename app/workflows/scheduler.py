import logging

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app.config import get_settings

logger = logging.getLogger(__name__)


def scan_for_meeting_reminders() -> None:
    logger.info("Meeting reminder scan completed; configure a notification adapter to deliver reminders.")


def create_scheduler() -> BackgroundScheduler:
    settings = get_settings()
    scheduler = BackgroundScheduler(timezone=settings.scheduler_timezone)
    scheduler.add_job(
        scan_for_meeting_reminders,
        trigger=IntervalTrigger(minutes=settings.reminder_scan_interval_minutes),
        id="meeting-reminder-scan",
        replace_existing=True,
    )
    return scheduler