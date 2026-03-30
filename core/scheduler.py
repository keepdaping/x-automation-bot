"""
Background scheduler for periodic housekeeping tasks.

FIXED:
- BlockingScheduler → BackgroundScheduler (no longer blocks main engagement loop)
- Removed BrowserManager instantiation from job (sync Playwright is not
  thread-safe; a second browser would also double detection risk)
- Removed broken start_feedback_analysis (referenced undefined variables/functions)

The outcome-checking job now marks pending interactions as "checked" via DB
only. Browser-based checks (got_reply_back, got_follow) cannot safely run in
a background thread with Playwright's sync API; they must be wired into the
main thread when that feature is needed.
"""

import random
from datetime import datetime, timezone

from logger_setup import log
from feedback import FeedbackTracker


# ---------------------------------------------------------------------------
# Job implementation
# ---------------------------------------------------------------------------

def _check_outcomes_job() -> None:
    """
    Periodic housekeeping: mark pending interactions as checked.

    Does NOT launch a browser. Marks rows older than 2 hours as checked
    so the interactions table does not accumulate indefinitely.
    Got_reply_back / got_follow / got_dm remain 0 until a main-thread
    outcome-checking mechanism is implemented.
    """
    try:
        log.info("Scheduler: running outcome housekeeping...")
        tracker = FeedbackTracker()
        now = datetime.now(timezone.utc).isoformat()

        tracker.conn.execute(
            """
            UPDATE interactions
            SET checked_at = ?
            WHERE checked_at IS NULL
              AND sent_at < datetime('now', '-2 hours')
            """,
            (now,),
        )
        updated = tracker.conn.execute("SELECT changes()").fetchone()[0]
        tracker.conn.commit()
        tracker.close()

        if updated > 0:
            log.info(f"Scheduler: marked {updated} interaction(s) as checked")

    except Exception as e:
        log.error(f"Scheduler housekeeping job failed: {e}")


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def start_scheduler():
    """
    Start the background scheduler and return the scheduler instance.

    Uses BackgroundScheduler so it runs in a daemon thread and does NOT
    block the caller. Returns None if APScheduler is not installed or
    startup fails — the bot continues running without it.
    """
    try:
        from apscheduler.schedulers.background import BackgroundScheduler
    except ImportError:
        log.warning("APScheduler not installed — outcome scheduler disabled")
        return None

    try:
        scheduler = BackgroundScheduler(daemon=True)
        interval_min = random.randint(90, 110)

        scheduler.add_job(
            _check_outcomes_job,
            trigger="interval",
            minutes=interval_min,
            id="outcome_check",
            replace_existing=True,
        )

        scheduler.start()
        log.info(
            f"Background scheduler started — housekeeping every ~{interval_min} min"
        )
        return scheduler

    except Exception as e:
        log.error(f"Failed to start background scheduler: {e}")
        return None
