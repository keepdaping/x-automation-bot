import sqlite3
import hashlib
from datetime import datetime, date, timezone
from pathlib import Path
from logger_setup import log
from config import Config

DB_PATH = Path("data/bot.db")
DB_PATH.parent.mkdir(exist_ok=True)


def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS posts (
            id INTEGER PRIMARY KEY,
            text_hash TEXT UNIQUE,
            tweet_id TEXT,
            topic TEXT,
            format TEXT,
            score REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS quote_tweets (
            id INTEGER PRIMARY KEY,
            original_id TEXT UNIQUE,
            our_tweet_id TEXT,
            created_at TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS replies (
            id INTEGER PRIMARY KEY,
            text_hash TEXT UNIQUE,
            our_tweet_id TEXT,
            replied_to_id TEXT UNIQUE,
            created_at TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS engagement_log (
            id INTEGER PRIMARY KEY,
            action TEXT,
            target_id TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
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


def save_post(text: str, tweet_id: str, topic: str, fmt: str, score: float):
    h = hashlib.sha256(text.encode()).hexdigest()

    conn = sqlite3.connect(DB_PATH)

    conn.execute(
        "INSERT INTO posts (text_hash, tweet_id, topic, format, score) VALUES (?,?,?,?,?)",
        (h, tweet_id, topic, fmt, score)
    )

    conn.commit()
    conn.close()


# --------------------------------------------------
# Daily post limit
# --------------------------------------------------

def count_posts_today() -> int:

    # Use UTC date to match posting window logic
    today_start = datetime.combine(datetime.now(timezone.utc).date(), datetime.min.time())
    today_start_str = today_start.strftime("%Y-%m-%d %H:%M:%S")

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute("""
        SELECT COUNT(*) 
        FROM posts 
        WHERE created_at >= ?
    """, (today_start_str,))

    count = cur.fetchone()[0]

    conn.close()

    return count


# --------------------------------------------------
# Daily post guard (persistent)
# --------------------------------------------------

def get_last_daily_post_date() -> date | None:
    """Return the UTC date of the most recent daily post (if any)."""

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute(
        """SELECT created_at FROM posts WHERE format = 'daily' ORDER BY created_at DESC LIMIT 1"""
    )
    row = cur.fetchone()
    conn.close()

    if not row or not row[0]:
        return None

    try:
        # SQLite stores timestamps as 'YYYY-MM-DD HH:MM:SS' (UTC)
        return datetime.fromisoformat(row[0]).date()
    except Exception:
        return None


def has_posted_today() -> bool:
    """Return True if a daily tweet has already been posted in UTC today."""
    last_date = get_last_daily_post_date()
    if not last_date:
        return False
    return last_date == datetime.now(timezone.utc).date()


# --------------------------------------------------
# Engagement logging
# --------------------------------------------------

def log_engagement(action: str, target_id: str):

    conn = sqlite3.connect(DB_PATH)

    conn.execute(
        "INSERT INTO engagement_log (action, target_id) VALUES (?, ?)",
        (action, target_id),
    )

    conn.commit()
    conn.close()


# --------------------------------------------------
# Rate limit counters
# --------------------------------------------------

def count_recent(action: str, minutes: int) -> int:

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute("""
        SELECT COUNT(*)
        FROM engagement_log
        WHERE action = ?
        AND timestamp >= datetime('now', ?)
    """, (action, f"-{minutes} minutes"))

    count = cur.fetchone()[0]

    conn.close()

    return count


# --------------------------------------------------
# Safety Guards
# --------------------------------------------------

def can_like() -> bool:

    recent = count_recent("like", 60)

    if recent >= Config.MAX_LIKES_PER_HOUR:
        log.info("Like limit reached for this hour")
        return False

    return True


def can_reply() -> bool:

    recent = count_recent("reply", 60)

    if recent >= Config.MAX_REPLIES_PER_HOUR:
        log.info("Reply limit reached for this hour")
        return False

    return True


def can_quote() -> bool:

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute("""
        SELECT COUNT(*)
        FROM quote_tweets
        WHERE created_at >= date('now')
    """)

    count = cur.fetchone()[0]

    conn.close()

    if count >= Config.MAX_QUOTES_PER_DAY:
        log.info("Daily quote limit reached")
        return False

    return True