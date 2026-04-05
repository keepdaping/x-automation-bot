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
    # Use SQLite's built-in UTC conversion so the comparison is timezone-consistent.
    # CURRENT_TIMESTAMP is stored as local time by SQLite; strftime with 'utc' modifier
    # normalises it regardless of server timezone.
    cur.execute(
        "SELECT strftime('%Y-%m-%d', created_at, 'utc') FROM posts "
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
