# core/scheduler.py

import random
from apscheduler.schedulers.blocking import BlockingScheduler
from logger_setup import log

from core.poster import post_tweet
from core.replier import reply_to_tweets
from core.quoter import quote_trending
from core.engagement import engage_with_posts
from core.thread_poster import post_thread


def start_scheduler(job_func, client):

    scheduler = BlockingScheduler()

    # Main tweet job
    scheduler.add_job(
        job_func,
        "interval",
        minutes=random.randint(90, 110)
    )

    # Reply engine
    scheduler.add_job(
        lambda: reply_to_tweets(client),
        "interval",
        minutes=random.randint(25, 40)
    )

    # Quote tweets
    scheduler.add_job(
        lambda: quote_trending(client),
        "interval",
        minutes=random.randint(120, 180)
    )

    # Engagement engine
    scheduler.add_job(
        lambda: engage_with_posts(client),
        "interval",
        minutes=random.randint(45, 70)
    )

    # Thread posting
    scheduler.add_job(
        lambda: post_thread(client),
        "interval",
        hours=random.randint(5, 7)
    )

    log.info("Scheduler started — growth engines active")

    try:
        scheduler.start()

    except (KeyboardInterrupt, SystemExit):

        scheduler.shutdown()