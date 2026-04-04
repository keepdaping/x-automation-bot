"""
Search phrase performance tracking and outcome reflection.
"""

import sqlite3
from logger_setup import log
from db.schema import DB_PATH


def init_search_log():
    """Ensure search_log table exists (idempotent — safe to call every run)."""
    conn = sqlite3.connect(DB_PATH)
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS search_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            phrase TEXT NOT NULL,
            tweets_found INTEGER DEFAULT 0,
            actions_taken INTEGER DEFAULT 0,
            high_intent_found INTEGER DEFAULT 0,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_search_log_phrase ON search_log(phrase);
        CREATE INDEX IF NOT EXISTS idx_search_log_time ON search_log(timestamp);
    """)
    conn.commit()
    conn.close()


def log_search(phrase: str, tweets_found: int,
               actions_taken: int = 0, high_intent_found: int = 0):
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute(
            "INSERT INTO search_log (phrase, tweets_found, actions_taken, high_intent_found) "
            "VALUES (?, ?, ?, ?)",
            (phrase, tweets_found, actions_taken, high_intent_found),
        )
        conn.commit()
    except Exception as e:
        log.warning(f"log_search failed: {e}")
    finally:
        conn.close()


def get_phrase_stats(days: int = 7) -> dict:
    """Returns {phrase: {searches, avg_tweets_found, avg_actions, avg_high_intent}}."""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT phrase,
                   COUNT(*)                 AS searches,
                   AVG(tweets_found)        AS avg_tweets,
                   AVG(actions_taken)       AS avg_actions,
                   AVG(high_intent_found)   AS avg_high_intent
            FROM search_log
            WHERE timestamp >= datetime('now', ?)
            GROUP BY phrase
        """, (f"-{days} days",))
        return {
            r[0]: {
                "searches": r[1],
                "avg_tweets_found": round(r[2] or 0, 2),
                "avg_actions": round(r[3] or 0, 2),
                "avg_high_intent": round(r[4] or 0, 2),
            }
            for r in cur.fetchall()
        }
    except Exception as e:
        log.warning(f"get_phrase_stats failed: {e}")
        return {}
    finally:
        conn.close()


def reflect_and_adapt():
    """
    Logs a Grok-style honest daily summary of reply outcomes and search phrase
    performance. Called automatically once per calendar day from the engagement loop.
    """
    from db.interactions import get_reply_outcomes  # local import — avoids circular dep at module level

    log.info("=" * 70)
    log.info("TRUTH-SEEKING SUMMARY (last 24h)")
    log.info("=" * 70)

    outcomes = get_reply_outcomes(days=1)
    phrase_stats = get_phrase_stats(days=1)

    if not outcomes and not phrase_stats:
        log.info("  No data yet — bot hasn't acted enough to reflect on.")
        log.info("=" * 70)
        return

    if outcomes:
        log.info("REPLY OUTCOMES:")
        for row in outcomes:
            total = row["total"]
            reply_rate = round((row["got_reply_back"] / total) * 100, 1) if total else 0
            dm_rate = round((row["got_dm"] / total) * 100, 1) if total else 0
            log.info(
                f"  [{row['intent']} / {row['reply_style']}] "
                f"{total} sent | {reply_rate}% got reply | {dm_rate}% got DM | "
                f"avg score={row['avg_outcome_score']}"
            )
            if total >= 3 and reply_rate == 0 and dm_rate == 0:
                log.warning(
                    f"  ⚠  HONEST: [{row['intent']} / {row['reply_style']}] "
                    f"0 replies on {total} attempts — this style isn't connecting."
                )
    else:
        log.info("  No replies sent in the last 24h.")

    if phrase_stats:
        log.info("SEARCH PHRASE PERFORMANCE:")
        sorted_phrases = sorted(
            phrase_stats.items(), key=lambda x: x[1]["avg_tweets_found"], reverse=True
        )
        for phrase, stats in sorted_phrases[:10]:
            log.info(
                f"  '{phrase}': {stats['avg_tweets_found']:.1f} avg tweets | "
                f"{stats['searches']} searches | {stats['avg_actions']:.1f} avg actions"
            )
            if stats["searches"] >= 3 and stats["avg_tweets_found"] < 0.5:
                log.warning(
                    f"  ⚠  LOW YIELD: '{phrase}' almost never finds tweets — deprioritize it."
                )
    else:
        log.info("  No search data in the last 24h.")

    log.info("=" * 70)


def optimize_and_reflect():
    """
    Logs the truth-seeking summary, then asks Claude for 3 new phrase suggestions
    based on the last 7 days of search performance. One Claude call per day.
    """
    reflect_and_adapt()

    stats = get_phrase_stats(days=7)
    if not stats:
        return

    sorted_stats = sorted(stats.items(), key=lambda x: x[1]["avg_tweets_found"], reverse=True)
    top_5 = sorted_stats[:5]
    bottom_5 = [s for s in sorted_stats if s[1]["avg_tweets_found"] < 0.5][-5:]

    top_summary = "\n".join(
        f"  '{p}': {d['avg_tweets_found']:.1f} avg tweets, {d['searches']} searches"
        for p, d in top_5
    )
    bottom_summary = "\n".join(
        f"  '{p}': {d['avg_tweets_found']:.1f} (failing)"
        for p, d in bottom_5
    ) or "  none"

    prompt = (
        f"Best-performing X search phrases (last 7 days):\n{top_summary}\n\n"
        f"Worst-performing phrases:\n{bottom_summary}\n\n"
        "Suggest exactly 3 NEW 2-5 word search phrases that real people tweet when "
        "struggling with automation, freelancing, or growing online. "
        "Different from the ones above. Output ONLY the 3 phrases, one per line, no numbering."
    )

    try:
        from core.generator import generate_contextual_reply  # late import — avoids circular dep
        suggestions_raw = generate_contextual_reply(
            tweet_text="",
            system_prompt="You are a search phrase optimizer. Output only raw phrases, one per line.",
            user_message=prompt,
            max_tokens=80,
        )
        if suggestions_raw:
            suggestions = [s.strip() for s in suggestions_raw.strip().splitlines() if s.strip()][:3]
            log.info(f"[optimize_and_reflect] Claude suggests new phrases: {suggestions}")
    except Exception as e:
        log.warning(f"[optimize_and_reflect] Phrase suggestion failed: {e}")
