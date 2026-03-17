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
