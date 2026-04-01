"""
Database operations for the bot.

Handles: posts, replies, engagement logging, follow tracking.
Dead code (can_like, can_reply, can_quote) removed - rate_limiter handles all limits.
"""

import sqlite3
import hashlib
from datetime import datetime, date, timezone
from pathlib import Path
from logger_setup import log
from config import Config

DB_PATH = Path(Config.DATABASE_PATH)
DB_PATH.parent.mkdir(exist_ok=True)


def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS posts (
            id INTEGER PRIMARY KEY,
            text_hash TEXT UNIQUE,
            tweet_id TEXT,
            topic TEXT,
            pillar TEXT,
            format TEXT,
            score REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS replies (
            id INTEGER PRIMARY KEY,
            text_hash TEXT UNIQUE,
            our_tweet_id TEXT,
            replied_to_id TEXT UNIQUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS engagement_log (
            id INTEGER PRIMARY KEY,
            action TEXT,
            target_id TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS follows (
            id INTEGER PRIMARY KEY,
            user_id TEXT UNIQUE,
            username TEXT,
            followed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            followed_back BOOLEAN DEFAULT FALSE,
            unfollowed_at TIMESTAMP
        );

                CREATE TABLE IF NOT EXISTS interactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sent_at TEXT NOT NULL,
            tweet_id TEXT,
            reply_id TEXT,
            user_handle TEXT,
            tweet_text TEXT,
            reply_text TEXT,
            intent TEXT,
            reply_style TEXT,
            got_reply_back INTEGER DEFAULT 0,
            got_follow INTEGER DEFAULT 0,
            got_dm INTEGER DEFAULT 0,
            checked_at TEXT,
            score INTEGER DEFAULT 0,
            llm_score INTEGER DEFAULT 0,
            conversation_turns INTEGER DEFAULT 0,
            outcome_score INTEGER DEFAULT 0
        );

        CREATE INDEX IF NOT EXISTS idx_follows_date ON follows(followed_at);
        CREATE INDEX IF NOT EXISTS idx_follows_unfollowed ON follows(unfollowed_at);

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
    log.info("Database initialized")


# --------------------------------------------------
# Duplicate protection
# --------------------------------------------------

def is_duplicate(text: str) -> bool:
    h = hashlib.sha256(text.encode()).hexdigest()
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM posts WHERE text_hash = ?", (h,))
    exists = cur.fetchone() is not None
    conn.close()
    return exists


def save_post(text: str, tweet_id: str, topic: str, fmt: str, score: float, pillar: str = ""):
    h = hashlib.sha256(text.encode()).hexdigest()
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "INSERT OR IGNORE INTO posts (text_hash, tweet_id, topic, pillar, format, score) VALUES (?,?,?,?,?,?)",
        (h, tweet_id, topic, pillar, fmt, score)
    )
    conn.commit()
    conn.close()


# --------------------------------------------------
# Daily post tracking
# --------------------------------------------------

def count_posts_today() -> int:
    today_start = datetime.combine(datetime.now(timezone.utc).date(), datetime.min.time())
    today_start_str = today_start.strftime("%Y-%m-%d %H:%M:%S")
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM posts WHERE created_at >= ?", (today_start_str,))
    count = cur.fetchone()[0]
    conn.close()
    return count


def get_last_daily_post_date() -> date | None:
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT created_at FROM posts WHERE format = 'daily' ORDER BY created_at DESC LIMIT 1")
    row = cur.fetchone()
    conn.close()
    if not row or not row[0]:
        return None
    try:
        return datetime.fromisoformat(row[0]).date()
    except Exception:
        return None


def has_posted_today() -> bool:
    last_date = get_last_daily_post_date()
    if not last_date:
        return False
    return last_date == datetime.now(timezone.utc).date()


# --------------------------------------------------
# Engagement logging
# --------------------------------------------------

def log_engagement(action: str, target_id: str):
    conn = sqlite3.connect(DB_PATH)
    conn.execute("INSERT INTO engagement_log (action, target_id) VALUES (?, ?)", (action, target_id))
    conn.commit()
    conn.close()


# --------------------------------------------------
# Follow tracking (for unfollow strategy)
# --------------------------------------------------

def save_follow(user_id: str, username: str = ""):
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "INSERT OR IGNORE INTO follows (user_id, username) VALUES (?, ?)",
        (user_id, username)
    )
    conn.commit()
    conn.close()


def get_stale_follows(days: int = 7, limit: int = 5) -> list:
    """Get users we followed who haven't followed back after N days."""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        SELECT user_id, username, followed_at FROM follows
        WHERE followed_back = FALSE
        AND unfollowed_at IS NULL
        AND followed_at <= datetime('now', ?)
        ORDER BY followed_at ASC
        LIMIT ?
    """, (f"-{days} days", limit))
    rows = cur.fetchall()
    conn.close()
    return [{"user_id": r[0], "username": r[1], "followed_at": r[2]} for r in rows]


def mark_unfollowed(user_id: str):
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "UPDATE follows SET unfollowed_at = CURRENT_TIMESTAMP WHERE user_id = ?",
        (user_id,)
    )
    conn.commit()
    conn.close()


def get_follow_stats() -> dict:
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM follows WHERE unfollowed_at IS NULL")
    active = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM follows WHERE unfollowed_at IS NOT NULL")
    unfollowed = cur.fetchone()[0]
    conn.close()
    return {"active_follows": active, "unfollowed": unfollowed}


# --------------------------------------------------
# Conversion tracking (lead generation)
# --------------------------------------------------

def init_conversion_tracking():
    """Create the conversion tracking table."""
    conn = sqlite3.connect(DB_PATH)
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS conversions (
            id INTEGER PRIMARY KEY,
            tweet_text TEXT,
            tweet_url TEXT,
            reply_text TEXT,
            keyword TEXT,
            intent_score INTEGER,
            intent_label TEXT,
            reply_type TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_conversions_intent ON conversions(intent_score);
        CREATE INDEX IF NOT EXISTS idx_conversions_date ON conversions(created_at);
    """)
    conn.commit()
    conn.close()


def log_conversion(tweet_text: str, tweet_url: str, reply_text: str,
                   keyword: str, intent_score: int, intent_label: str,
                   reply_type: str = "standard"):
    """Log a high-value engagement for tracking."""
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """INSERT INTO conversions 
           (tweet_text, tweet_url, reply_text, keyword, intent_score, intent_label, reply_type) 
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (tweet_text[:500], tweet_url, reply_text[:500], keyword, intent_score, intent_label, reply_type)
    )
    conn.commit()
    conn.close()


def get_recent_conversions(days: int = 7, limit: int = 50) -> list:
    """Get recent high-intent engagements for the dashboard."""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        SELECT tweet_text, reply_text, keyword, intent_score, intent_label, reply_type, created_at
        FROM conversions
        WHERE created_at >= datetime('now', ?)
        ORDER BY intent_score DESC, created_at DESC
        LIMIT ?
    """, (f"-{days} days", limit))
    rows = cur.fetchall()
    conn.close()
    return [
        {"tweet": r[0], "reply": r[1], "keyword": r[2], "intent_score": r[3],
         "intent_label": r[4], "reply_type": r[5], "date": r[6]}
        for r in rows
    ]


def get_conversion_stats() -> dict:
    """Get conversion tracking stats."""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    try:
        cur.execute("SELECT COUNT(*) FROM conversions")
        total = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM conversions WHERE intent_score = 3")
        high = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM conversions WHERE intent_score = 2")
        medium = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM conversions WHERE reply_type = 'curiosity'")
        curiosity = cur.fetchone()[0]
        cur.execute("SELECT keyword, COUNT(*) as cnt FROM conversions GROUP BY keyword ORDER BY cnt DESC LIMIT 5")
        top_keywords = [{"keyword": r[0], "count": r[1]} for r in cur.fetchall()]
    except Exception:
        total = high = medium = curiosity = 0
        top_keywords = []
    conn.close()
    return {"total": total, "high_intent": high, "medium_intent": medium, "curiosity_replies": curiosity, "top_keywords": top_keywords}


# --------------------------------------------------
# Search log (phrase performance tracking)
# --------------------------------------------------

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


# --------------------------------------------------
# Outcome reflection
# --------------------------------------------------

def get_reply_outcomes(days: int = 7) -> list:
    """Returns success rates per intent + reply_style over the last N days."""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT intent, reply_style,
                   COUNT(*)              AS total,
                   SUM(got_reply_back)   AS replies,
                   SUM(got_follow)       AS follows,
                   SUM(got_dm)           AS dms,
                   AVG(outcome_score)    AS avg_score
            FROM interactions
            WHERE sent_at >= datetime('now', ?)
            GROUP BY intent, reply_style
            ORDER BY avg_score DESC
        """, (f"-{days} days",))
        return [
            {
                "intent": r[0],
                "reply_style": r[1],
                "total": r[2],
                "got_reply_back": r[3] or 0,
                "got_follow": r[4] or 0,
                "got_dm": r[5] or 0,
                "avg_outcome_score": round(r[6] or 0, 2),
            }
            for r in cur.fetchall()
        ]
    except Exception as e:
        log.warning(f"get_reply_outcomes failed: {e}")
        return []
    finally:
        conn.close()


def reflect_and_adapt():
    """
    Logs a Grok-style honest daily summary of reply outcomes and search phrase
    performance. Called automatically once per calendar day from the engagement loop.
    """
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
