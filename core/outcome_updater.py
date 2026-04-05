"""
OutcomeUpdater — reads pending interactions and writes back real outcome signals.

Two modes:
  mark_stale_as_checked()     — DB-only, safe for background scheduler thread
  check_pending_with_page()   — Playwright browser checks, call from MAIN THREAD only

The split exists because Playwright's sync API is not thread-safe.
"""

import sqlite3
import time
from datetime import datetime, timezone
from typing import List

from db.schema import DB_PATH
from logger_setup import log


# Max outcome_score denominator for reward normalisation (reply=3, follow=2, dm=5 → max 10)
_MAX_OUTCOME_SCORE = 10.0


class OutcomeUpdater:

    # ─── DB-only (background-safe) ────────────────────────────────────────

    def mark_stale_as_checked(self, hours: int = 48) -> int:
        """
        Mark old unchecked interactions as checked so they don't accumulate.
        Safe to call from APScheduler background thread (no browser needed).
        Returns number of rows updated.
        """
        now = datetime.now(timezone.utc).isoformat()
        conn = sqlite3.connect(str(DB_PATH))
        try:
            conn.execute(
                """
                UPDATE interactions
                SET checked_at = ?
                WHERE checked_at IS NULL
                  AND sent_at < datetime('now', ?)
                """,
                (now, f"-{hours} hours"),
            )
            updated = conn.execute("SELECT changes()").fetchone()[0]
            conn.commit()
            if updated:
                log.info(f"[OutcomeUpdater] Marked {updated} stale interaction(s) as checked")
            return updated
        except Exception as e:
            log.warning(f"[OutcomeUpdater] mark_stale_as_checked failed: {e}")
            return 0
        finally:
            conn.close()

    def get_pending_checks(self, limit: int = 8) -> List[dict]:
        """
        Return interactions that are old enough to have generated a response
        but have not yet been browser-checked.
        Called from main thread before check_pending_with_page().
        """
        conn = sqlite3.connect(str(DB_PATH))
        try:
            cur = conn.execute(
                """
                SELECT reply_id, user_handle, tweet_text, intent, reply_style
                FROM interactions
                WHERE checked_at IS NULL
                  AND reply_id IS NOT NULL AND reply_id != ''
                  AND sent_at < datetime('now', '-2 hours')
                  AND sent_at > datetime('now', '-48 hours')
                ORDER BY sent_at DESC
                LIMIT ?
                """,
                (limit,),
            )
            cols = [d[0] for d in cur.description]
            return [dict(zip(cols, row)) for row in cur.fetchall()]
        except Exception as e:
            log.warning(f"[OutcomeUpdater] get_pending_checks failed: {e}")
            return []
        finally:
            conn.close()

    # ─── Browser-based (main thread only) ─────────────────────────────────

    def check_pending_with_page(self, page, limit: int = 5) -> int:
        """
        Use Playwright page to detect: did the user reply back? did they follow?
        MUST be called from the main thread (sync Playwright constraint).

        Returns count of rows updated.
        """
        pending = self.get_pending_checks(limit=limit)
        if not pending:
            return 0

        updated = 0
        now = datetime.now(timezone.utc).isoformat()
        conn = sqlite3.connect(str(DB_PATH))

        try:
            for item in pending:
                reply_id = item.get("reply_id", "")
                user_handle = item.get("user_handle", "")

                got_reply_back = 0
                got_follow = 0

                # Check if user replied to our reply.
                # Selector strategy: look for an article containing a link to the
                # user's profile (data-testid="User-Name" with href="/{handle}").
                # This is more reliable than :has-text('@handle') because:
                #   1. The '@' symbol may not appear in article text — it appears
                #      in the username chip which uses aria/link attributes.
                #   2. href-based matching works even if display name differs.
                if reply_id:
                    try:
                        page.goto(
                            f"https://x.com/i/status/{reply_id}",
                            wait_until="domcontentloaded",
                            timeout=8000,
                        )
                        time.sleep(1.5)
                        if user_handle:
                            # Primary selector: profile link inside a reply article
                            handle_lower = user_handle.lstrip("@").lower()
                            selector = (
                                f"article a[href='/{handle_lower}'], "
                                f"article a[href='/@{handle_lower}']"
                            )
                            try:
                                el = page.locator(selector).first
                                if el.is_visible(timeout=2000):
                                    got_reply_back = 1
                            except Exception:
                                # Fallback: text-based check (less reliable but safe)
                                try:
                                    fallback = page.locator(
                                        f"article:has-text('{handle_lower}')"
                                    ).first
                                    if fallback.is_visible(timeout=1500):
                                        got_reply_back = 1
                                except Exception:
                                    pass
                    except Exception:
                        pass

                # Check if user followed us back
                if user_handle:
                    try:
                        page.goto(
                            f"https://x.com/{user_handle}",
                            wait_until="domcontentloaded",
                            timeout=8000,
                        )
                        time.sleep(1.0)
                        btn = page.locator("div[role='button']:has-text('Following')").first
                        if btn.is_visible(timeout=2000):
                            got_follow = 1
                    except Exception:
                        pass

                # Compute outcome_score as an absolute value, not incremental.
                # Using `outcome_score + delta` risks double-counting if this row
                # is checked multiple times before checked_at is committed.
                # Instead, SET to the derived value directly (idempotent).
                # DM component (×5) stays at its existing value since DM detection
                # is not implemented in the browser check path.
                absolute_score = got_reply_back * 3 + got_follow * 2

                conn.execute(
                    """
                    UPDATE interactions
                    SET got_reply_back = MAX(got_reply_back, ?),
                        got_follow     = MAX(got_follow, ?),
                        outcome_score  = MAX(outcome_score,
                                             ? + (got_dm * 5)),
                        checked_at     = ?
                    WHERE reply_id = ? AND checked_at IS NULL
                    """,
                    (got_reply_back, got_follow, absolute_score, now, reply_id),
                )
                rows_changed = conn.execute("SELECT changes()").fetchone()[0]
                updated += rows_changed

            conn.commit()

        except Exception as e:
            log.warning(f"[OutcomeUpdater] Browser check failed: {e}")
        finally:
            conn.close()

        if updated:
            log.info(f"[OutcomeUpdater] Browser-checked {updated} interaction(s)")
        return updated

    # ─── Helper: normalise outcome_score to [0, 1] for bandit reward ──────

    @staticmethod
    def normalise_score(outcome_score: float) -> float:
        return min(1.0, max(0.0, outcome_score / _MAX_OUTCOME_SCORE))


# ─── Module-level singleton ────────────────────────────────────────────────

_updater: OutcomeUpdater = None


def get_outcome_updater() -> OutcomeUpdater:
    global _updater
    if _updater is None:
        _updater = OutcomeUpdater()
    return _updater
