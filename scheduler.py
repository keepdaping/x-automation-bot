# scheduler.py
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.interval import IntervalTrigger
from config import Config
from logger_setup import log


def build_scheduler(job_func) -> BlockingScheduler:
    """
    Configure and return a BlockingScheduler that calls `job_func`
    every Config.MIN_INTERVAL_MINUTES minutes.

    max_instances=1 ensures the job never overlaps with itself.
    coalesce=True   ensures missed runs fire once, not multiple times.
    """
    scheduler = BlockingScheduler(timezone="UTC")

    scheduler.add_job(
        job_func,
        trigger=IntervalTrigger(minutes=Config.MIN_INTERVAL_MINUTES),
        id="post_job",
        max_instances=1,
        coalesce=True,
    )

    log.info(f"Scheduler configured — interval: every {Config.MIN_INTERVAL_MINUTES} minutes.")
    return scheduler
