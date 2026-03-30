"""
Phase 4: Basic queue (thread-safe, no external Redis yet)
"""

from queue import Queue
from threading import Thread
import time
from logger_setup import log

job_queue = Queue()

def enqueue_engagement(job):
    job_queue.put(job)
    log.info(f"Queued engagement job for {job.get('user_handle')}")

def start_worker():
    def worker_loop():
        while True:
            job = job_queue.get()
            from core.engagement import _process_single_tweet  # reuse existing
            # run job...
            job_queue.task_done()
    Thread(target=worker_loop, daemon=True).start()