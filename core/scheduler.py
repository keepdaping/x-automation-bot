"""
Scheduler for periodic background tasks (outcome checking, etc.).
"""

import random
from datetime import datetime
from apscheduler.schedulers.blocking import BlockingScheduler

from logger_setup import log
from feedback import FeedbackTracker
from browser.browser_manager import BrowserManager


def start_scheduler():
    """
    Start the background scheduler for outcome checking.
    Runs every ~90-110 minutes (randomized for human-like behavior).
    """
    scheduler = BlockingScheduler()

    def check_outcomes_job():
        """Background job: check pending replies/follows for outcomes."""
        try:
            log.info("Scheduler: Checking pending interaction outcomes...")
            tracker = FeedbackTracker()
            browser_mgr = BrowserManager()
            page = browser_mgr.start()   # Light browser for checks

            cur = tracker.conn.execute("""
                SELECT id, reply_id, user_handle 
                FROM interactions 
                WHERE checked_at IS NULL 
                  AND sent_at > datetime('now', '-24 hours')
                ORDER BY sent_at DESC
                LIMIT 20
            """)
            pending = cur.fetchall()

            updated = 0
            for row_id, reply_id, handle in pending:
                if not handle:
                    continue
                try:
                    is_following = browser_mgr.check_is_following(handle)
                    has_replied = browser_mgr.check_user_replied(reply_id, handle) if reply_id else False
                    has_dm = browser_mgr.check_for_dm(handle)  # placeholder

                    score = (3 if has_replied else 0) + (5 if is_following else 0) + (10 if has_dm else 0)

                    tracker.conn.execute("""
                        UPDATE interactions
                        SET got_reply_back = ?, got_follow = ?, got_dm = ?,
                            checked_at = ?, score = ?
                        WHERE id = ?
                    """, (int(has_replied), int(is_following), int(has_dm),
                          datetime.utcnow().isoformat(), score, row_id))
                    tracker.conn.commit()
                    updated += 1
                except Exception as e:
                    log.warning(f"Outcome check failed for @{handle}: {e}")

            log.info(f"Checked {len(pending)} interactions, updated {updated}")
            tracker.close()
            browser_mgr.close()

        except Exception as e:
            log.error(f"Scheduler job failed: {e}")

    # Schedule the job
    interval_min = random.randint(90, 110)
    scheduler.add_job(
        check_outcomes_job,
        "interval",
        minutes=interval_min,
        id="outcome_check",
        replace_existing=True
    )

    log.info(f"Scheduler started — outcome checking every ~{interval_min} minutes")

    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        log.info("Scheduler shutting down...")
        scheduler.shutdown()

    # Phase 3: Self-improving feedback job
def start_feedback_analysis():
    if not Config.FEEDBACK_ANALYSIS_ENABLED:
        return
    # Your existing APScheduler code – add:
    scheduler.add_job(analyze_winning_replies, 'cron', day_of_week='sun', hour=3)
    log.info("✅ Self-improving feedback loop scheduled (weekly)")