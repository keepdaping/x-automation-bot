import sqlite3
import hashlib
from datetime import datetime, date
from pathlib import Path
from logger_setup import log

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
            our_tweet_id TEXT,
            replied_to_id TEXT UNIQUE,
            created_at TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS engagement_log (
            id INTEGER PRIMARY KEY,
            action TEXT,
            target_id TEXT,
            timestamp TIMESTAMP
        );
    """)
    conn.commit()
    conn.close()
    log.info("Database initialized")

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
    conn.execute("INSERT INTO posts (text_hash, tweet_id, topic, format, score) VALUES (?,?,?,?,?)",
                 (h, tweet_id, topic, fmt, score))
    conn.commit()
    conn.close()

# Add more helper functions for quotes, replies, etc. (all implemented in full version)


def count_posts_today() -> int:
    """
    Count how many posts were made today (UTC date).
    Used to enforce daily post cap.
    """
    today_start = datetime.combine(date.today(), datetime.min.time())
    today_start_str = today_start.isoformat()

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