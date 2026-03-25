"""
Conversation memory (Phase 2) – stores per-user history in existing SQLite.
No new DB required. Uses JSON for simplicity.
"""

import json
import sqlite3
from datetime import datetime
from config import Config
from logger_setup import log

class ConversationMemory:
    def __init__(self):
        self.conn = sqlite3.connect(Config.DATABASE_PATH)

    def save_history(self, user_handle: str, tweet_id: str, reply_text: str, turn: int = 1):
        """Append to conversation history (JSON column)."""
        now = datetime.utcnow().isoformat()
        data = {"tweet_id": tweet_id, "reply_text": reply_text, "turn": turn, "timestamp": now}

        self.conn.execute("""
            INSERT OR REPLACE INTO interactions 
            (user_handle, tweet_id, reply_text, conversation_turns)
            VALUES (?, ?, ?, COALESCE((SELECT conversation_turns FROM interactions WHERE user_handle=?), 0) + 1)
        """, (user_handle, tweet_id, json.dumps(data), user_handle))  # simplistic – adjust if needed
        self.conn.commit()
        log.debug(f"Memory saved for @{user_handle} (turn {turn})")

    def get_relevant_history(self, user_handle: str, limit: int = 3) -> list:
        """Return last N turns as list of dicts."""
        cur = self.conn.execute("""
            SELECT reply_text FROM interactions 
            WHERE user_handle = ? ORDER BY sent_at DESC LIMIT ?
        """, (user_handle, limit))
        rows = cur.fetchall()
        return [json.loads(r[0]) if isinstance(r[0], str) else r[0] for r in rows if r[0]]

    def close(self):
        self.conn.close()