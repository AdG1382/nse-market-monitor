"""Runs data collection + report generation on a fixed daily schedule."""

import atexit

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from config import REPORT_SCHEDULE, TIMEZONE
from db import save_snapshots
from market_data import fetch_all_snapshots
from reports import build_report

_scheduler: BackgroundScheduler | None = None


def collect_and_report(report_type: str):
    print(f"[scheduler] running {report_type} job")
    try:
        snaps = fetch_all_snapshots()
        save_snapshots(snaps)
        build_report(report_type)
    except Exception as exc:
        # A failed run must not kill the job; the next one may well succeed.
        print(f"[scheduler] {report_type} job failed: {exc}")
        return
    print(f"[scheduler] {report_type} job done ({len(snaps)} sessions)")


def start_scheduler() -> BackgroundScheduler:
    """Start the background scheduler, or return the running one.

    Guarded because the app module is imported once per worker (and again by
    uvicorn's reloader); starting twice would double every scheduled job.
    """
    global _scheduler
    if _scheduler is not None and _scheduler.running:
        return _scheduler

    _scheduler = BackgroundScheduler(timezone=TIMEZONE)

    for report_type, time_str in REPORT_SCHEDULE.items():
        hour, minute = (int(x) for x in time_str.split(":"))
        _scheduler.add_job(
            collect_and_report,
            CronTrigger(hour=hour, minute=minute, timezone=TIMEZONE),
            args=[report_type],
            id=report_type,
            replace_existing=True,
        )

    _scheduler.start()
    atexit.register(shutdown_scheduler)
    return _scheduler


def shutdown_scheduler():
    global _scheduler
    if _scheduler is not None and _scheduler.running:
        _scheduler.shutdown(wait=False)
    _scheduler = None
