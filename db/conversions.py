"""
Conversion tracking — high-intent engagement logging for the dashboard.
"""

import sqlite3
from db.schema import DB_PATH


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
