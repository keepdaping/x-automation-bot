"""
Database path resolution and schema initialization.
All tables and indexes are created here. Every other db module imports DB_PATH from here.
"""

import sqlite3
from pathlib import Path
from logger_setup import log
from config import Config

DB_PATH = Path(Config.DATABASE_PATH)
DB_PATH.parent.mkdir(exist_ok=True)


def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
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
