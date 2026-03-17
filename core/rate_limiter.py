"""
Core rate limiting system. Added unfollow support.
"""

import sqlite3
import time
import math
import threading
from datetime import datetime, timedelta, date
from pathlib import Path
from logger_setup import log

DB_PATH = Path("data/rate_limiter.db")
DB_PATH.parent.mkdir(exist_ok=True)


class RateLimiter:
    def __init__(self, config):
        self.config = config
        self.db_lock = threading.Lock()
        self.db = sqlite3.connect(str(DB_PATH), check_same_thread=False)
        self._init_db()

        self.daily_limits = {
            "like": getattr(config, "MAX_LIKES_PER_DAY", 20),
            "reply": getattr(config, "MAX_REPLIES_PER_DAY", 5),
            "follow": getattr(config, "MAX_FOLLOWS_PER_DAY", 10),
            "unfollow": getattr(config, "MAX_UNFOLLOWS_PER_DAY", 5),
            "post": getattr(config, "MAX_POSTS_PER_DAY", 2),
            "quote": getattr(config, "MAX_QUOTES_PER_DAY", 2),
        }

        self.hourly_limits = {
            "like": max(1, math.ceil(self.daily_limits["like"] / 12)),
            "reply": max(1, math.ceil(self.daily_limits["reply"] / 12)),
            "follow": max(1, math.ceil(self.daily_limits["follow"] / 12)),
            "unfollow": max(1, math.ceil(self.daily_limits["unfollow"] / 12)),
            "post": max(1, math.ceil(self.daily_limits["post"] / 6)),
            "quote": max(1, math.ceil(self.daily_limits["quote"] / 6)),
        }

        self.min_action_spacing = {
            "like": 30,
            "reply": 120,
            "follow": 60,
            "unfollow": 60,
            "post": 300,
            "quote": 180,
        }

    def _init_db(self):
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS action_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                action_type TEXT NOT NULL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                success BOOLEAN DEFAULT TRUE,
                duration_ms INTEGER,
                target_id TEXT,
                notes TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_action_time ON action_history(action_type, timestamp);
            CREATE TABLE IF NOT EXISTS daily_summary (
                date DATE PRIMARY KEY,
                likes INTEGER DEFAULT 0,
                replies INTEGER DEFAULT 0,
                follows INTEGER DEFAULT 0,
                unfollows INTEGER DEFAULT 0,
                posts INTEGER DEFAULT 0,
                quotes INTEGER DEFAULT 0,
                errors INTEGER DEFAULT 0
            );
        """)
        self.db.commit()
        # Auto-migrate: add missing columns to old databases
        self._migrate_db()

    def _migrate_db(self):
        """Add missing columns to existing databases (backward compatibility)."""
        try:
            cur = self.db.execute("PRAGMA table_info(daily_summary)")
            existing_cols = {row[1] for row in cur.fetchall()}
            needed = {"likes", "replies", "follows", "unfollows", "posts", "quotes", "errors"}
            for col in needed - existing_cols:
                self.db.execute(f"ALTER TABLE daily_summary ADD COLUMN {col} INTEGER DEFAULT 0")
            self.db.commit()
        except Exception as e:
            pass  # Table might not exist yet, _init_db will create it

    def can_perform_action(self, action_type: str) -> tuple:
        with self.db_lock:
            self.reset_if_new_day()
            if action_type not in self.daily_limits:
                return False, f"Unknown action: {action_type}"

            daily_count = self._count_actions(action_type, period="day")
            if daily_count >= self.daily_limits[action_type]:
                return False, f"Daily {action_type} limit reached"

            hourly_count = self._count_actions(action_type, period="hour")
            if hourly_count >= self.hourly_limits[action_type]:
                return False, f"Hourly {action_type} limit reached"

            recent_count = self._count_actions(action_type, minutes=2)
            if recent_count >= 5:
                return False, f"Cluster detected: {recent_count} {action_type}(s) in 2 min"

            global_cluster = self._count_all_actions(minutes=10)
            if global_cluster >= 8:
                return False, f"Global cluster: {global_cluster} actions in 10 min"

            time_since_last = self._time_since_last_action(action_type)
            min_spacing = self.min_action_spacing.get(action_type, 30)
            if time_since_last is not None and time_since_last < min_spacing:
                return False, f"Too soon, {min_spacing - time_since_last:.0f}s remaining"

            return True, ""

    def record_action(self, action_type: str, success: bool = True, duration_ms: int = 0, target_id: str = None, notes: str = None):
        try:
            with self.db_lock:
                self.db.execute(
                    "INSERT INTO action_history (action_type, success, duration_ms, target_id, notes) VALUES (?, ?, ?, ?, ?)",
                    (action_type, success, duration_ms, target_id, notes)
                )
                self.db.commit()
                if success:
                    self._update_daily_summary(action_type)
        except Exception as e:
            log.error(f"Failed to record action: {e}")

    def _count_actions(self, action_type: str, period: str = None, minutes: int = None) -> int:
        if minutes is not None:
            cutoff = datetime.now() - timedelta(minutes=minutes)
        elif period == "hour":
            cutoff = datetime.now() - timedelta(hours=1)
        elif period == "day":
            cutoff = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        else:
            return 0
        cur = self.db.execute(
            "SELECT COUNT(*) FROM action_history WHERE action_type = ? AND timestamp > ? AND success = TRUE",
            (action_type, cutoff)
        )
        return cur.fetchone()[0]

    def _count_all_actions(self, minutes: int = 10) -> int:
        cutoff = datetime.now() - timedelta(minutes=minutes)
        cur = self.db.execute("SELECT COUNT(*) FROM action_history WHERE timestamp > ? AND success = TRUE", (cutoff,))
        return cur.fetchone()[0]

    def _time_since_last_action(self, action_type: str) -> int:
        cur = self.db.execute(
            "SELECT timestamp FROM action_history WHERE action_type = ? AND success = TRUE ORDER BY timestamp DESC LIMIT 1",
            (action_type,)
        )
        result = cur.fetchone()
        if not result:
            return None
        last_timestamp = datetime.fromisoformat(result[0])
        return int((datetime.now() - last_timestamp).total_seconds())

    def _update_daily_summary(self, action_type: str):
        today = date.today()
        column_map = {"like": "likes", "reply": "replies", "follow": "follows", "unfollow": "unfollows", "post": "posts", "quote": "quotes", "error": "errors"}
        col = column_map.get(action_type)
        if not col:
            return
        try:
            cur = self.db.execute(f"SELECT {col} FROM daily_summary WHERE date = ?", (today,))
            row = cur.fetchone()
            if row:
                self.db.execute(f"UPDATE daily_summary SET {col} = ? WHERE date = ?", (row[0] + 1, today))
            else:
                self.db.execute(f"INSERT INTO daily_summary (date, {col}) VALUES (?, 1)", (today,))
            self.db.commit()
        except Exception as e:
            log.error(f"Failed to update daily summary: {e}")

    def get_daily_summary(self) -> dict:
        today = date.today()
        cur = self.db.execute("SELECT likes, replies, follows, unfollows, posts, quotes, errors FROM daily_summary WHERE date = ?", (today,))
        row = cur.fetchone()
        if not row:
            return {"likes": 0, "replies": 0, "follows": 0, "unfollows": 0, "posts": 0, "quotes": 0, "errors": 0}
        return {"likes": row[0], "replies": row[1], "follows": row[2], "unfollows": row[3], "posts": row[4], "quotes": row[5], "errors": row[6]}

    def get_remaining_actions(self) -> dict:
        summary = self.get_daily_summary()
        remaining = {}
        for action_type, limit in self.daily_limits.items():
            used = summary.get(action_type, 0)
            remaining[action_type] = max(0, limit - used)
        return remaining

    def reset_if_new_day(self):
        last_date = self._get_last_recorded_date()
        today = date.today()
        if last_date and last_date < today:
            log.info(f"New day: {last_date} → {today}")
            cutoff_date = today - timedelta(days=30)
            self.db.execute("DELETE FROM daily_summary WHERE date < ?", (cutoff_date,))
            cutoff_history = datetime.now() - timedelta(days=90)
            self.db.execute("DELETE FROM action_history WHERE timestamp < ?", (cutoff_history,))
            self.db.commit()

    def _get_last_recorded_date(self) -> date:
        cur = self.db.execute("SELECT MAX(date) FROM daily_summary")
        result = cur.fetchone()
        if result and result[0]:
            return datetime.fromisoformat(result[0]).date()
        return None

    def export_metrics(self) -> dict:
        return {"daily_summary": self.get_daily_summary(), "remaining_today": self.get_remaining_actions(), "limits": self.daily_limits}


_rate_limiter: RateLimiter = None

def init_rate_limiter(config) -> RateLimiter:
    global _rate_limiter
    _rate_limiter = RateLimiter(config)
    return _rate_limiter

def get_rate_limiter() -> RateLimiter:
    global _rate_limiter
    if _rate_limiter is None:
        raise RuntimeError("Rate limiter not initialized")
    return _rate_limiter
