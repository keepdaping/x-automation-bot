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
    Periodic housekeeping: mark stale interactions as checked via OutcomeUpdater.

    Does NOT launch a browser — DB-only, safe for background thread.
    Browser-based outcome checks (got_reply_back, got_follow) happen in the
    main engagement thread via OutcomeUpdater.check_pending_with_page().
    """
    try:
        log.info("Scheduler: running outcome housekeeping...")
        from core.outcome_updater import get_outcome_updater
        updated = get_outcome_updater().mark_stale_as_checked(hours=48)
        if updated > 0:
            log.info(f"Scheduler: marked {updated} interaction(s) as checked")
    except Exception as e:
        log.error(f"Scheduler housekeeping job failed: {e}")


def _run_learning_job() -> None:
    """Daily learning loop — updates bandit rewards from interaction outcomes."""
    try:
        from core.learning import run_learning_cycle
        run_learning_cycle()
    except Exception as e:
        log.error(f"Scheduler learning job failed: {e}")


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

        # Daily learning loop — runs once every 24h (randomised offset avoids
        # thundering-herd if multiple bots ever run on the same machine)
        learning_offset_min = random.randint(0, 60)
        scheduler.add_job(
            _run_learning_job,
            trigger="interval",
            hours=24,
            minutes=learning_offset_min,
            id="learning_cycle",
            replace_existing=True,
        )

        scheduler.start()
        log.info(
            f"Background scheduler started — "
            f"housekeeping every ~{interval_min} min, "
            f"learning every 24h (+{learning_offset_min}m offset)"
        )
        return scheduler

    except Exception as e:
        log.error(f"Failed to start background scheduler: {e}")
        return None
