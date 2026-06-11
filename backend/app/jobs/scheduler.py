from datetime import datetime, timedelta

import structlog
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.date import DateTrigger

from app.core.config import settings

logger = structlog.get_logger()

_scheduler: AsyncIOScheduler | None = None


async def _scrape_job():
    logger.info("Scheduled scrape starting")
    try:
        from app.services.scraper_service import run_scrape
        await run_scrape()
    except Exception as e:
        logger.error("Scheduled scrape failed", error=str(e))


async def start_scheduler() -> AsyncIOScheduler:
    global _scheduler
    _scheduler = AsyncIOScheduler()

    _scheduler.add_job(
        _scrape_job,
        trigger=IntervalTrigger(hours=settings.scrape_interval_hours),
        id="scrape_job",
        name="Apartment scraper",
        replace_existing=True,
    )

    _scheduler.start()
    logger.info("Scheduler started", interval_hours=settings.scrape_interval_hours)

    # Run initial scrape 15 seconds after startup (let app + Telegram fully start)
    _scheduler.add_job(
        _scrape_job,
        trigger=DateTrigger(run_date=datetime.utcnow() + timedelta(seconds=15)),
        id="initial_scrape",
        name="Initial scrape (delayed)",
    )

    return _scheduler


def stop_scheduler(scheduler: AsyncIOScheduler | None = None):
    s = scheduler or _scheduler
    if s:
        s.shutdown(wait=False)
        logger.info("Scheduler stopped")
