"""
Follow and unfollow tracking.
"""

import sqlite3
from db.schema import DB_PATH


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
