# core/scheduler.py
# Only used in run.py (local / Docker mode)

from apscheduler.schedulers.blocking import BlockingScheduler
from logger_setup import log


def start_scheduler(job_func):
    scheduler = BlockingScheduler()
    scheduler.add_job(job_func, 'interval', minutes=95 + random.randint(-12, 12))
    log.info("Scheduler started — running every ~90–110 minutes")
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()