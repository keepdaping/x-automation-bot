"""
Core rate limiting system to prevent bot detection.

Enforces:
- Daily action limits (likes, replies, follows, posts)
- Hourly action distribution (prevents action clustering)
- Cluster detection (5+ actions within 2 minutes)
- Action spacing (minimum delay between same actions)
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
    """Global rate limiting to prevent X detection"""
    
    def __init__(self, config):
        """
        Initialize rate limiter
        
        Args:
            config: Config object with rate limit settings
        """
        self.config = config
        
        # Use threading lock to prevent race conditions
        self.db_lock = threading.Lock()
        
        # Database connection - no check_same_thread since we use lock now
        self.db = sqlite3.connect(str(DB_PATH), check_same_thread=False)
        self._init_db()
        
        # Daily action limits (from config)
        self.daily_limits = {
            "like": getattr(config, "MAX_LIKES_PER_DAY", 20),
            "reply": getattr(config, "MAX_REPLIES_PER_DAY", 5),
            "follow": getattr(config, "MAX_FOLLOWS_PER_DAY", 10),
            "post": getattr(config, "MAX_POSTS_PER_DAY", 2),
        }
        
        # Hourly limits (distributed from daily using ceiling division)
        # Use ceiling to ensure proper distribution and never round down to 0
        self.hourly_limits = {
            "like": max(1, math.ceil(self.daily_limits["like"] / 12)),
            "reply": max(1, math.ceil(self.daily_limits["reply"] / 12)),
            "follow": max(1, math.ceil(self.daily_limits["follow"] / 12)),
            "post": max(1, math.ceil(self.daily_limits["post"] / 6)),
        }
        
        # Minimum seconds between same action (spread them out)
        self.min_action_spacing = {
            "like": 30,      # At least 30s between likes
            "reply": 120,    # At least 2min between replies
            "follow": 60,    # At least 1min between follows
            "post": 300,     # At least 5min between posts
        }
    
    def _init_db(self):
        """Initialize rate limiter database"""
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
            
            CREATE INDEX IF NOT EXISTS idx_action_time 
                ON action_history(action_type, timestamp);
            
            CREATE INDEX IF NOT EXISTS idx_success 
                ON action_history(success);
            
            CREATE TABLE IF NOT EXISTS daily_summary (
                date DATE PRIMARY KEY,
                likes INTEGER DEFAULT 0,
                replies INTEGER DEFAULT 0,
                follows INTEGER DEFAULT 0,
                posts INTEGER DEFAULT 0,
                errors INTEGER DEFAULT 0
            );
        """)
        self.db.commit()
    
    def can_perform_action(self, action_type: str) -> tuple:
        """
        Check if action can be performed right now
        
        Returns:
            (allowed: bool, reason: str) - reason is empty if allowed
        """
        
        with self.db_lock:  # Thread-safe database access
            # Clean up old daily records if new day detected
            self.reset_if_new_day()
            
            if action_type not in self.daily_limits:
                return False, f"Unknown action type: {action_type}"
            
            # Check 1: Daily limit
            daily_count = self._count_actions(action_type, period="day")
            daily_limit = self.daily_limits[action_type]
            
            if daily_count >= daily_limit:
                return False, f"Daily {action_type} limit reached ({daily_limit})"
            
            # Check 2: Hourly limit (distribution check)
            hourly_count = self._count_actions(action_type, period="hour")
            hourly_limit = self.hourly_limits[action_type]
            
            if hourly_count >= hourly_limit:
                return False, f"Hourly {action_type} limit reached ({hourly_limit})"
            
            # Check 3: Per-action-type cluster detection (5+ of same action in 2 minutes)
            recent_count = self._count_actions(action_type, minutes=2)
            if recent_count >= 5:
                return False, f"Action cluster detected! {recent_count} {action_type}(s) in 2 min"
            
            # Check 3b: GLOBAL cluster detection (8+ total actions in 10 minutes)
            # This prevents 4 likes + 4 replies + 4 follows = 12 total (undetected)
            global_cluster = self._count_all_actions(minutes=10)
            if global_cluster >= 8:
                return False, f"Global action cluster detected! {global_cluster} actions in 10 min"
            
            # Check 4: Action spacing (prevent rapid-fire actions)
            time_since_last = self._time_since_last_action(action_type)
            min_spacing = self.min_action_spacing[action_type]
            
            if time_since_last is not None and time_since_last < min_spacing:
                return False, f"Too soon, {min_spacing - time_since_last:.0f}s remaining"
            
            # All checks passed
            return True, ""
    
    def record_action(self, action_type: str, success: bool = True, 
                     duration_ms: int = 0, target_id: str = None, notes: str = None):
        """
        Record an action that was performed
        
        Args:
            action_type: Type of action (like, reply, follow, post)
            success: Whether action succeeded
            duration_ms: How long action took
            target_id: ID of target (tweet ID, user ID, etc)
            notes: Additional notes for debugging
        """
        
        try:
            with self.db_lock:  # Thread-safe database write
                self.db.execute(
                    """INSERT INTO action_history 
                       (action_type, success, duration_ms, target_id, notes)
                       VALUES (?, ?, ?, ?, ?)""",
                    (action_type, success, duration_ms, target_id, notes)
                )
                self.db.commit()
                
                # Update daily summary
                if success:
                    self._update_daily_summary(action_type)
                
                log.debug(f"✓ Recorded {action_type} (success={success}, {duration_ms}ms)")
            
        except Exception as e:
            log.error(f"Failed to record action: {e}")
    
    def _count_actions(self, action_type: str, period: str = None, minutes: int = None) -> int:
        """
        Count actions in a time period
        
        Args:
            action_type: Type of action to count
            period: "day" or "hour"
            minutes: Count actions in last N minutes (overrides period)
            
        Returns:
            Number of successful actions in period
        """
        
        if minutes is not None:
            # Count actions in last N minutes
            cutoff = datetime.now() - timedelta(minutes=minutes)
        elif period == "hour":
            # Count actions in last hour
            cutoff = datetime.now() - timedelta(hours=1)
        elif period == "day":
            # Count actions since start of today
            now = datetime.now()
            cutoff = now.replace(hour=0, minute=0, second=0, microsecond=0)
        else:
            return 0
        
        cur = self.db.execute(
            """SELECT COUNT(*) FROM action_history 
               WHERE action_type = ? AND timestamp > ? AND success = TRUE""",
            (action_type, cutoff)
        )
        
        return cur.fetchone()[0]
    
    def _count_all_actions(self, minutes: int = 10) -> int:
        """
        Count ALL actions (across all types) in last N minutes
        
        This detects global clustering: e.g., 4 likes + 4 replies + 4 follows = 12 total
        
        Args:
            minutes: Count actions in last N minutes
            
        Returns:
            Total count of successful actions in period
        """
        
        cutoff = datetime.now() - timedelta(minutes=minutes)
        cur = self.db.execute(
            """SELECT COUNT(*) FROM action_history 
               WHERE timestamp > ? AND success = TRUE""",
            (cutoff,)
        )
        return cur.fetchone()[0]
    
    def _time_since_last_action(self, action_type: str) -> int:
        """
        Get seconds since last action of this type
        
        Returns:
            Seconds since last action, or None if no history
        """
        
        cur = self.db.execute(
            """SELECT timestamp FROM action_history 
               WHERE action_type = ? AND success = TRUE
               ORDER BY timestamp DESC LIMIT 1""",
            (action_type,)
        )
        
        result = cur.fetchone()
        if not result:
            return None
        
        last_timestamp = datetime.fromisoformat(result[0])
        elapsed = (datetime.now() - last_timestamp).total_seconds()
        
        return int(elapsed)
    
    def _update_daily_summary(self, action_type: str):
        """Update daily summary counts"""
        
        today = date.today()
        count_column = action_type
        
        try:
            # Check if today's record exists
            cur = self.db.execute(
                f"SELECT {count_column} FROM daily_summary WHERE date = ?",
                (today,)
            )
            
            row = cur.fetchone()
            
            if row:
                # Update existing
                new_count = row[0] + 1
                self.db.execute(
                    f"UPDATE daily_summary SET {count_column} = ? WHERE date = ?",
                    (new_count, today)
                )
            else:
                # Create new daily record
                self.db.execute(
                    f"""INSERT INTO daily_summary (date, {count_column}) 
                       VALUES (?, 1)""",
                    (today,)
                )
            
            self.db.commit()
            
        except Exception as e:
            log.error(f"Failed to update daily summary: {e}")
    
    def get_daily_summary(self) -> dict:
        """Get today's action summary"""
        
        today = date.today()
        cur = self.db.execute(
            """SELECT likes, replies, follows, posts, errors 
               FROM daily_summary WHERE date = ?""",
            (today,)
        )
        
        row = cur.fetchone()
        
        if not row:
            return {
                "likes": 0,
                "replies": 0,
                "follows": 0,
                "posts": 0,
                "errors": 0,
            }
        
        return {
            "likes": row[0],
            "replies": row[1],
            "follows": row[2],
            "posts": row[3],
            "errors": row[4],
        }
    
    def get_remaining_actions(self) -> dict:
        """Get remaining actions today"""
        
        summary = self.get_daily_summary()
        remaining = {}
        
        for action_type, limit in self.daily_limits.items():
            used = summary.get(action_type, 0)
            remaining[action_type] = max(0, limit - used)
        
        return remaining
    
    def reset_if_new_day(self):
        """Reset counts if it's a new day - clean up old daily records"""
        
        last_date = self._get_last_recorded_date()
        today = date.today()
        
        if last_date and last_date < today:
            log.info(f"✓ New day detected ({last_date} → {today}), cleaning up old records")
            
            # Delete daily summary records older than 30 days
            cutoff_date = today - timedelta(days=30)
            self.db.execute(
                "DELETE FROM daily_summary WHERE date < ?",
                (cutoff_date,)
            )
            self.db.commit()
            
            # Also delete old action history (keep 90 days)
            cutoff_history = datetime.now() - timedelta(days=90)
            self.db.execute(
                "DELETE FROM action_history WHERE timestamp < ?",
                (cutoff_history,)
            )
            self.db.commit()
            
            log.debug(f"Cleaned up records older than {cutoff_date}")
    
    def _get_last_recorded_date(self) -> date:
        """Get date of last recorded action"""
        
        cur = self.db.execute(
            "SELECT MAX(date) FROM daily_summary"
        )
        result = cur.fetchone()
        
        if result and result[0]:
            return datetime.fromisoformat(result[0]).date()
        return None
    
    def export_metrics(self) -> dict:
        """Export rate limiter metrics"""
        
        remaining = self.get_remaining_actions()
        summary = self.get_daily_summary()
        
        return {
            "daily_summary": summary,
            "remaining_today": remaining,
            "limits": self.daily_limits,
        }


# Global instance (initialized by bot)
_rate_limiter: RateLimiter = None


def init_rate_limiter(config) -> RateLimiter:
    """Initialize global rate limiter"""
    global _rate_limiter
    _rate_limiter = RateLimiter(config)
    return _rate_limiter


def get_rate_limiter() -> RateLimiter:
    """Get global rate limiter instance"""
    global _rate_limiter
    if _rate_limiter is None:
        raise RuntimeError("Rate limiter not initialized. Call init_rate_limiter() first.")
    return _rate_limiter
