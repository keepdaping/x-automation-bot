"""
Daily Learning Loop — runs once every 24 hours via APScheduler.

Responsibilities:
  1. Push yesterday's reply-style outcomes into the reply-style bandit
  2. Push last 7 days of phrase performance into the phrase bandit
     (conversion-yield weighted, not just tweet-volume weighted)
  3. Log a human-readable summary of what changed and why

Design rules:
  - DB-only (no browser, safe for scheduler background thread)
  - Idempotent within the same calendar day (guarded by _last_run_date)
  - Feeds directly into bandit state; policy engine reads bandit state on next cycle
  - Never modifies Config or any other module — only writes to bandit_arms table
"""

import sqlite3
from datetime import date

from db.schema import DB_PATH
from logger_setup import log

_last_run_date: date = None


def run_learning_cycle() -> None:
    """
    Entry point called by the scheduler once per day.
    Guards against double-execution within the same calendar day.
    """
    global _last_run_date
    today = date.today()
    if _last_run_date == today:
        return
    _last_run_date = today

    log.info("=" * 60)
    log.info("LEARNING CYCLE — START")
    log.info("=" * 60)

    try:
        _update_reply_bandit()
    except Exception as e:
        log.warning(f"[Learning] Reply bandit update failed (non-fatal): {e}")

    try:
        _update_phrase_bandit()
    except Exception as e:
        log.warning(f"[Learning] Phrase bandit update failed (non-fatal): {e}")

    try:
        _log_summary()
    except Exception as e:
        log.warning(f"[Learning] Summary log failed (non-fatal): {e}")

    log.info("LEARNING CYCLE — COMPLETE")


# ─── Reply style bandit ───────────────────────────────────────────────────

def _update_reply_bandit() -> None:
    """
    Read checked interactions from the past 24 hours grouped by reply_style.
    Push normalised avg_outcome_score as reward into the UCB1 bandit.

    Data quality guard:
      The background scheduler marks rows as checked_at after 48h WITHOUT running
      a browser check ("phantom zeros").  Rows that were stale-batch-marked and
      had outcome_score=0 are therefore unreliable negative signals.

      Filter strategy: only include rows where EITHER
        (a) outcome_score > 0  — confirmed positive signal
        (b) sent_at is older than 48h  — true zero (browser check window has passed)
      This excludes the noisy 2–48h band that might not have been browser-checked.

    Normalisation: reward = outcome_score / 10.0 (max theoretical = 10)
    Minimum 3 interactions per style before pushing (n >= 3).
    """
    from core.bandit import get_reply_bandit

    conn = sqlite3.connect(str(DB_PATH))
    try:
        cur = conn.execute(
            """
            SELECT reply_style,
                   COUNT(*)           AS n,
                   AVG(outcome_score) AS avg_score,
                   SUM(CASE WHEN outcome_score > 0 THEN 1 ELSE 0 END) AS positive_n
            FROM interactions
            WHERE sent_at    > datetime('now', '-48 hours')
              AND reply_style IN ('grok', 'curiosity', 'standard')
              AND checked_at IS NOT NULL
              AND (
                    outcome_score > 0
                    OR sent_at < datetime('now', '-48 hours')
              )
            GROUP BY reply_style
            HAVING n >= 3
            """,
        )
        rows = cur.fetchall()
    finally:
        conn.close()

    if not rows:
        log.info("[Learning] Insufficient quality interactions in last 48h — reply bandit unchanged")
        return

    bandit = get_reply_bandit()
    for style, n, avg_score, positive_n in rows:
        # Normalise to [0, 1] (max theoretical score = 10)
        reward = min(1.0, max(0.0, (avg_score or 0.0) / 10.0))
        bandit.update(style, reward)
        log.info(
            f"[Learning] Reply bandit: '{style}' → "
            f"reward={reward:.4f}  (n={n}, positive={positive_n}, raw_avg={avg_score:.3f})"
        )


# ─── Phrase bandit ────────────────────────────────────────────────────────

def _update_phrase_bandit() -> None:
    """
    Read search_log for the past 7 days with recency weighting.

    Time-decay rationale:
      A phrase that was dead last week but is performing well this week should
      not be dragged down by old data.  We apply a 2× weight to searches from
      the past 48 hours vs the older 5-day window using a weighted SQL query.
      This is equivalent to a simple two-tier exponential decay without requiring
      any additional columns or external libraries.

    Conversion yield formula:
      yield = (weighted_high_intent * 2 + weighted_actions * 0.5) / weighted_searches
      Capped at 3.0 to keep UCB1 confidence bounds reasonable.
      High-intent signals weighted 2× over raw actions — a high-intent tweet
      that triggers a reply is much more valuable than a generic tweet that
      got liked.

    Minimum 2 searches before updating (prevents single-use noise).
    """
    from core.bandit import get_phrase_bandit
    from config import Config

    conn = sqlite3.connect(str(DB_PATH))
    try:
        cur = conn.execute(
            """
            SELECT phrase,
                   SUM(weight)                      AS weighted_searches,
                   SUM(high_intent_found * weight)  AS weighted_hi,
                   SUM(actions_taken * weight)      AS weighted_act,
                   COUNT(*)                         AS raw_searches
            FROM (
                SELECT phrase, high_intent_found, actions_taken,
                       CASE
                           WHEN timestamp > datetime('now', '-2 days') THEN 2
                           ELSE 1
                       END AS weight
                FROM search_log
                WHERE timestamp > datetime('now', '-7 days')
            ) weighted
            GROUP BY phrase
            HAVING raw_searches >= 2
            """,
        )
        rows = cur.fetchall()
    finally:
        conn.close()

    if not rows:
        log.info("[Learning] Not enough phrase data yet — phrase bandit unchanged")
        return

    phrases = list(getattr(Config, "SEARCH_PHRASES", Config.SEARCH_KEYWORDS))
    if not phrases:
        return

    bandit = get_phrase_bandit(phrases)
    updated = 0
    for phrase, w_searches, w_hi, w_act, raw_searches in rows:
        if phrase not in bandit.arms:
            continue
        w_searches = max(w_searches or 1, 1)
        conversion_yield = min(
            3.0,
            ((w_hi or 0) * 2.0 + (w_act or 0) * 0.5) / w_searches,
        )
        bandit.update(phrase, conversion_yield)
        updated += 1
        log.debug(
            f"[Learning] Phrase bandit: '{phrase}' → "
            f"yield={conversion_yield:.3f}  "
            f"(raw_searches={raw_searches}, w_hi={w_hi:.1f}, w_act={w_act:.1f})"
        )

    log.info(f"[Learning] Phrase bandit: updated {updated} phrase(s) with time-decayed rewards")


# ─── Summary ─────────────────────────────────────────────────────────────

def _log_summary() -> None:
    """Log current bandit state + reward aggregator snapshot for observability."""
    from core.bandit import get_reply_bandit
    from core.reward_aggregator import get_reward_aggregator

    # --- Reply bandit state ---
    log.info("[Learning] Reply style bandit (current state):")
    stats = get_reply_bandit().get_stats()
    if stats:
        for style, s in sorted(stats.items(), key=lambda x: -x[1]["avg_reward"]):
            log.info(
                f"  {style:<12}  trials={s['trials']:>4}  "
                f"avg_reward={s['avg_reward']:.4f}  "
                f"total_reward={s['total_reward']:.3f}"
            )
    else:
        log.info("  (no data yet)")

    # --- Intent breakdown ---
    log.info("[Learning] Outcome by intent (last 7 days):")
    agg = get_reward_aggregator()
    intent_data = agg.get_by_intent(days=7)
    if intent_data:
        for intent_label, s in sorted(intent_data.items()):
            log.info(
                f"  {intent_label:<8}  trials={s['trials']:>4}  "
                f"avg_score={s['avg_outcome_score']:.4f}"
            )
    else:
        log.info("  (no data yet)")

    # --- Top / bottom phrases ---
    log.info("[Learning] Top search phrases by conversion_yield (last 7 days):")
    kw_data = agg.get_by_keyword(days=7)
    if kw_data:
        sorted_kw = sorted(
            kw_data.items(), key=lambda x: -x[1]["conversion_yield"]
        )
        for phrase, s in sorted_kw[:5]:
            log.info(
                f"  '{phrase[:40]}'  "
                f"yield={s['conversion_yield']:.3f}  "
                f"hi={s['avg_high_intent']:.1f}  searches={s['searches']}"
            )
        # Flag underperformers
        for phrase, s in sorted_kw:
            if s["searches"] >= 3 and s["conversion_yield"] < 0.1:
                log.warning(
                    f"  ⚠ LOW YIELD: '{phrase}' conversion_yield={s['conversion_yield']:.3f} "
                    f"over {s['searches']} searches — bandit will naturally deprioritise it"
                )
    else:
        log.info("  (no data yet)")
