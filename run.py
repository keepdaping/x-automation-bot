# core/scheduler.py

import random
from apscheduler.schedulers.blocking import BlockingScheduler
from logger_setup import log


def start_scheduler(job_func):

    scheduler = BlockingScheduler()

    interval = random.randint(90, 110)

    scheduler.add_job(
        job_func,
        "interval",
        minutes=interval
    )

    log.info(f"Scheduler started — running every ~{interval} minutes")

    try:

        scheduler.start()

    except (KeyboardInterrupt, SystemExit):

        scheduler.shutdown()