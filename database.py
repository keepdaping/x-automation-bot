# database.py
"""
SQLite persistence layer.

Tables:
  posts             — every tweet attempt (posted / failed / rejected)
  liked_tweets      — tweet IDs we have liked, with timestamp
  engagement_log    — every engagement action (like / reply) for rate-limit queries
  replied_tweets    — dedup store: one reply per author per source tweet
  greeting_log      — one row per calendar day when a greeting was prepended
"""
from __future__ import annotations

import os
import sqlite3
from datetime import date, datetime, timezone, timedelta
from contextlib import contextmanager
from config import Config
from logger_setup import log


os.makedirs(os.path.dirname(Config.DB_PATH) or ".", exist_ok=True)


# ── DDL ───────────────────────────────────────────────────────────────────────

_CREATE_POSTS_TABLE = """
CREATE TABLE IF NOT EXISTS posts (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    content          TEXT    NOT NULL,
    content_hash     TEXT    UNIQUE NOT NULL,
    source           TEXT    NOT NULL,
    topic            TEXT,
    tweet_id         TEXT,
    status           TEXT    NOT NULL,
    rejection_reason TEXT,
    created_at       TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);
"""

_CREATE_LIKED_TABLE = """
CREATE TABLE IF NOT EXISTS liked_tweets (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    tweet_id   TEXT    NOT NULL UNIQUE,
    liked_at   TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);
"""

_CREATE_ENGAGEMENT_LOG_TABLE = """
CREATE TABLE IF NOT EXISTS engagement_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    action      TEXT    NOT NULL,
    tweet_id    TEXT    NOT NULL,
    author_id   TEXT,
    created_at  TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);
"""

_CREATE_REPLIED_TABLE = """
CREATE TABLE IF NOT EXISTS replied_tweets (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    source_tweet_id TEXT    NOT NULL,
    reply_tweet_id  TEXT    NOT NULL,
    author_id       TEXT    NOT NULL,
    replied_at      TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    UNIQUE(source_tweet_id, author_id)
);
"""

_CREATE_GREETING_LOG_TABLE = """
CREATE TABLE IF NOT EXISTS greeting_log (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    greeting_date TEXT   NOT NULL UNIQUE,   -- ISO date: YYYY-MM-DD
    greeted_at   TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);
"""

_CREATE_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_posts_created_at     ON posts          (created_at);",
    "CREATE INDEX IF NOT EXISTS idx_posts_hash           ON posts          (content_hash);",
    "CREATE INDEX IF NOT EXISTS idx_liked_tweet_id       ON liked_tweets   (tweet_id);",
    "CREATE INDEX IF NOT EXISTS idx_engagement_action    ON engagement_log (action, created_at);",
    "CREATE INDEX IF NOT EXISTS idx_replied_author       ON replied_tweets (author_id, replied_at);",
]


# ── Connection ────────────────────────────────────────────────────────────────

@contextmanager
def _conn():
    con = sqlite3.connect(Config.DB_PATH, check_same_thread=False)
    con.execute("PRAGMA journal_mode=WAL;")
    con.execute("PRAGMA foreign_keys=ON;")
    try:
        yield con
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()


# ── Init ──────────────────────────────────────────────────────────────────────

def init_db() -> None:
    with _conn() as con:
        for stmt in [
            _CREATE_POSTS_TABLE,
            _CREATE_LIKED_TABLE,
            _CREATE_ENGAGEMENT_LOG_TABLE,
            _CREATE_REPLIED_TABLE,
            _CREATE_GREETING_LOG_TABLE,
        ]:
            con.execute(stmt)
        for idx in _CREATE_INDEXES:
            con.execute(idx)
    log.debug(f"Database ready at '{Config.DB_PATH}'")


# ── Posts ─────────────────────────────────────────────────────────────────────

def is_hash_seen(content_hash: str) -> bool:
    with _conn() as con:
        row = con.execute(
            "SELECT 1 FROM posts WHERE content_hash = ? AND status = 'posted' LIMIT 1",
            (content_hash,),
        ).fetchone()
    return row is not None


def posts_today() -> int:
    today = date.today().isoformat()
    with _conn() as con:
        row = con.execute(
            "SELECT COUNT(*) FROM posts WHERE status = 'posted' AND created_at LIKE ?",
            (f"{today}%",),
        ).fetchone()
    return row[0] if row else 0


def last_posted_at() -> datetime | None:
    with _conn() as con:
        row = con.execute(
            "SELECT created_at FROM posts WHERE status = 'posted' ORDER BY id DESC LIMIT 1"
        ).fetchone()
    if row is None:
        return None
    return datetime.fromisoformat(row[0].rstrip("Z"))


def record_post(
    *,
    content: str,
    content_hash: str,
    source: str,
    topic: str,
    tweet_id: str | None,
    status: str,
    rejection_reason: str | None = None,
) -> None:
    with _conn() as con:
        con.execute(
            """
            INSERT OR IGNORE INTO posts
                (content, content_hash, source, topic, tweet_id, status, rejection_reason)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (content, content_hash, source, topic, tweet_id, status, rejection_reason),
        )


# ── Likes ─────────────────────────────────────────────────────────────────────

def is_tweet_liked(tweet_id: str) -> bool:
    with _conn() as con:
        row = con.execute(
            "SELECT 1 FROM liked_tweets WHERE tweet_id = ? LIMIT 1",
            (tweet_id,),
        ).fetchone()
    return row is not None


def record_like(tweet_id: str) -> None:
    with _conn() as con:
        con.execute(
            "INSERT OR IGNORE INTO liked_tweets (tweet_id) VALUES (?)", (tweet_id,)
        )
        con.execute(
            "INSERT INTO engagement_log (action, tweet_id) VALUES ('like', ?)", (tweet_id,)
        )


# ── Replies ───────────────────────────────────────────────────────────────────

def has_replied_to_author(source_tweet_id: str, author_id: str) -> bool:
    with _conn() as con:
        row = con.execute(
            "SELECT 1 FROM replied_tweets WHERE source_tweet_id = ? AND author_id = ? LIMIT 1",
            (source_tweet_id, author_id),
        ).fetchone()
    return row is not None


def record_reply(*, source_tweet_id: str, reply_tweet_id: str, author_id: str) -> None:
    with _conn() as con:
        con.execute(
            "INSERT OR IGNORE INTO replied_tweets (source_tweet_id, reply_tweet_id, author_id) VALUES (?, ?, ?)",
            (source_tweet_id, reply_tweet_id, author_id),
        )
        con.execute(
            "INSERT INTO engagement_log (action, tweet_id, author_id) VALUES ('reply', ?, ?)",
            (reply_tweet_id, author_id),
        )


# ── Rate-limit counters ───────────────────────────────────────────────────────

def engagement_count_last_hour(action: str) -> int:
    cutoff = (
        datetime.now(timezone.utc) - timedelta(hours=1)
    ).strftime("%Y-%m-%dT%H:%M:%S")
    with _conn() as con:
        row = con.execute(
            "SELECT COUNT(*) FROM engagement_log WHERE action = ? AND created_at >= ?",
            (action, cutoff),
        ).fetchone()
    return row[0] if row else 0


# ── Greeting ──────────────────────────────────────────────────────────────────

def has_greeted_today() -> bool:
    """Return True if a greeting has already been logged for today (local date)."""
    today = date.today().isoformat()
    with _conn() as con:
        row = con.execute(
            "SELECT 1 FROM greeting_log WHERE greeting_date = ? LIMIT 1", (today,)
        ).fetchone()
    return row is not None


def record_greeting() -> None:
    """Mark today as greeted. Safe to call even if already recorded (INSERT OR IGNORE)."""
    today = date.today().isoformat()
    with _conn() as con:
        con.execute(
            "INSERT OR IGNORE INTO greeting_log (greeting_date) VALUES (?)", (today,)
        )
