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
            score INTEGER DEFAULT 0
        );

        CREATE INDEX IF NOT EXISTS idx_follows_date ON follows(followed_at);
        CREATE INDEX IF NOT EXISTS idx_follows_unfollowed ON follows(unfollowed_at);
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
