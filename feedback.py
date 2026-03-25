"""
Feedback loop for reply tracking - logs every sent reply and tracks outcomes.
Reuses your existing bot.db from database.py.
"""

import sqlite3
from datetime import datetime
from logger_setup import log
from config import Config


class FeedbackTracker:
    """Tracks replies and their outcomes (reply back / follow / DM)."""

    def __init__(self):
        self.conn = sqlite3.connect(Config.DATABASE_PATH)
        self._init_table()

    def _init_table(self):
        """Create interactions table if it doesn't exist with all migration columns."""
        self.conn.execute("""
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
            )
        """)
        self.conn.commit()

    def log_reply(self, tweet_id: str, reply_id: str, user_handle: str,
                  tweet_text: str, reply_text: str, intent: str, reply_style: str = "default"):
        """Log a reply right after it's successfully sent."""
        now = datetime.utcnow().isoformat()
        self.conn.execute("""
            INSERT INTO interactions 
            (sent_at, tweet_id, reply_id, user_handle, tweet_text, reply_text, intent, reply_style,
             llm_score, conversation_turns, outcome_score)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, 0, 0)
        """, (now, tweet_id, reply_id, user_handle, tweet_text[:500], reply_text[:500], intent, reply_style))
        self.conn.commit()
        log.info(f"[Feedback] Logged reply | Intent: {intent} | Style: {reply_style} | @{user_handle}")

    def get_stats(self):
        """Return simple stats for dashboard or manual review."""
        cur = self.conn.execute("""
            SELECT intent, reply_style, COUNT(*) as total,
                   SUM(got_reply_back) as replies,
                   SUM(got_follow) as follows,
                   SUM(got_dm) as dms,
                   AVG(score) as avg_score
            FROM interactions 
            GROUP BY intent, reply_style
            ORDER BY avg_score DESC
        """)
        return cur.fetchall()

    def close(self):
        self.conn.close()

    def update_outcome(self, reply_id: str, got_reply_back: int = 0, got_follow: int = 0, got_dm: int = 0):
        """Phase 3: Self-improving feedback – called by scheduler."""
        self.conn.execute("""
            UPDATE interactions SET 
                got_reply_back = ?, 
                got_follow = ?, 
                got_dm = ?,
                outcome_score = (got_reply_back * 3 + got_follow * 2 + got_dm * 5)
            WHERE reply_id = ?
        """, (got_reply_back, got_follow, got_dm, reply_id))
        self.conn.commit()