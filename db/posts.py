"""
Post deduplication and daily tweet tracking.
"""

import sqlite3
import hashlib
from datetime import datetime, date, timezone

from db.schema import DB_PATH


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
    # SQLite CURRENT_TIMESTAMP is always UTC — no modifier needed.
    # Do NOT apply the 'utc' modifier: it would treat the already-UTC value as local
    # time and subtract the timezone offset a second time, returning the wrong date.
    cur.execute(
        "SELECT strftime('%Y-%m-%d', created_at) FROM posts "
        "WHERE format = 'daily' ORDER BY created_at DESC LIMIT 1"
    )
    row = cur.fetchone()
    conn.close()
    if not row or not row[0]:
        return None
    try:
        return date.fromisoformat(row[0])
    except Exception:
        return None


def has_posted_today() -> bool:
    last_date = get_last_daily_post_date()
    if not last_date:
        return False
    return last_date == datetime.now(timezone.utc).date()


def count_daily_posts_today() -> int:
    """Hard DB gate: count 'daily' format posts for the current UTC calendar day.

    Uses SQLite's date('now') which is always UTC — independent of server timezone
    and of any in-memory flag state.  Returns ≥1 if a daily tweet was already saved
    today, 0 otherwise.
    """
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        "SELECT COUNT(*) FROM posts "
        "WHERE format = 'daily' AND date(created_at) = date('now')"
    )
    count = cur.fetchone()[0]
    conn.close()
    return count
