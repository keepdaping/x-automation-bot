"""
Human-like session behavior manager.

Instead of running continuous engagement loops, the bot operates in realistic sessions:
- Sessions: 20-45 minute periods of activity
- Breaks: 30-120 minute rest periods
- Active hours: 8 AM - 11 PM (configurable)
- Natural distribution: Actions spread throughout session with pauses

This makes the bot indistinguishable from natural user behavior.
"""

import random
import time
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional
from pathlib import Path
from logger_setup import log


class SessionState(Enum):
    """Session state machine"""
    IDLE = "idle"                    # Waiting to start session
    ACTIVE_SESSION = "active"        # In session, can perform actions
    BREAK = "break"                  # Between sessions, do not engage
    OUTSIDE_HOURS = "outside_hours"  # Outside active hours


class SessionManager:
    """Manages human-like session behavior and timing"""
    
    def __init__(self, config):
        """
        Initialize session manager
        
        Args:
            config: Config object with timing settings
        """
        self.config = config
        
        # Session timing (from config)
        self.session_duration_min = getattr(config, "SESSION_DURATION_MIN", 20)
        self.session_duration_max = getattr(config, "SESSION_DURATION_MAX", 45)
        
        # Break timing (from config)
        self.break_duration_min = getattr(config, "BREAK_DURATION_MIN", 30)
        self.break_duration_max = getattr(config, "BREAK_DURATION_MAX", 120)
        
        # Active hours (from config)
        self.active_start_hour = getattr(config, "ACTIVE_START_HOUR", 8)
        self.active_end_hour = getattr(config, "ACTIVE_END_HOUR", 23)
        
        # Action pacing within session
        self.min_action_interval_sec = getattr(config, "MIN_ACTION_INTERVAL_SEC", 30)
        self.max_action_interval_sec = getattr(config, "MAX_ACTION_INTERVAL_SEC", 180)
        
        # Behavioral randomization (from simulation analysis)
        self.session_continue_probability = getattr(config, "SESSION_CONTINUE_PROBABILITY", 0.25)
        self.extended_break_probability = getattr(config, "SESSION_EXTENDED_BREAK_PROBABILITY", 0.20)
        self.extended_break_min_hours = getattr(config, "SESSION_EXTENDED_BREAK_MIN_HOURS", 2)
        self.extended_break_max_hours = getattr(config, "SESSION_EXTENDED_BREAK_MAX_HOURS", 4)
        self.first_action_delay_min = getattr(config, "FIRST_ACTION_DELAY_SEC_MIN", 30)
        self.first_action_delay_max = getattr(config, "FIRST_ACTION_DELAY_SEC_MAX", 120)
        self.browse_only_probability = getattr(config, "SESSION_BROWSE_ONLY_PROBABILITY", 0.10)
        
        # Session state
        self.current_state = SessionState.IDLE
        self.session_start_time: Optional[datetime] = None
        self.session_duration_sec: Optional[int] = None
        self.break_start_time: Optional[datetime] = None
        self.break_duration_sec: Optional[int] = None
        
        # Action tracking
        self.last_action_time: Optional[datetime] = None
        self.actions_in_session = 0
        self.session_action_target: Optional[int] = None
        self.session_continuation = False  # Whether session was extended
        
        # Persistence file for session state
        self.state_file = Path("data/session_state.txt")
        self.state_file.parent.mkdir(exist_ok=True)
        
        # Load persisted state if exists
        self._load_state()
        
        log.info(f"✓ Session Manager initialized")
        log.info(f"  Active hours: {self.active_start_hour}:00 - {self.active_end_hour}:00")
        log.info(f"  Session: {self.session_duration_min}-{self.session_duration_max} min")
        log.info(f"  Breaks: {self.break_duration_min}-{self.break_duration_max} min")
        log.info(f"  Randomization: {int(self.session_continue_probability*100)}% session continue, {int(self.extended_break_probability*100)}% extended breaks")
    
    def should_be_active(self) -> bool:
        """
        Check if bot should be active right now
        
        Returns:
            True if within active hours and not in break period
        """
        
        # Check if outside active hours
        now_hour = datetime.now().hour
        if now_hour < self.active_start_hour or now_hour >= self.active_end_hour:
            self.current_state = SessionState.OUTSIDE_HOURS
            return False
        
        # Check if in break period
        if self.is_in_break():
            self.current_state = SessionState.BREAK
            return False
        
        # Active hours, not in break
        return True
    
    def start_session(self) -> bool:
        """
        Start a new engagement session
        
        Returns:
            True if session started, False if already in session
        """
        
        if self.current_state == SessionState.ACTIVE_SESSION:
            return False
        
        # Randomize session duration (20-45 min)
        self.session_duration_sec = random.randint(
            self.session_duration_min * 60,
            self.session_duration_max * 60
        )
        
        self.session_start_time = datetime.now()
        self.actions_in_session = 0
        self.session_continuation = False
        
        # Delay first action (30-120 sec) - humans don't act immediately
        first_action_delay = random.randint(self.first_action_delay_min, self.first_action_delay_max)
        self.last_action_time = self.session_start_time - timedelta(seconds=first_action_delay)
        
        # Calculate target actions for this session
        # Example: 30-min session with 2-3 cycles = 6-10 actions
        session_minutes = self.session_duration_sec / 60
        self.session_action_target = max(2, int(session_minutes / 5))  # ~1 action per 5 min
        
        self.current_state = SessionState.ACTIVE_SESSION
        
        session_end = self.session_start_time + timedelta(seconds=self.session_duration_sec)
        log.info(f"\n{'='*70}")
        log.info(f"📱 SESSION START")
        log.info(f"   Duration: {self.session_duration_sec/60:.0f} min")
        log.info(f"   Target actions: {self.session_action_target}")
        log.info(f"   Session until: {session_end.strftime('%H:%M:%S')}")
        log.info(f"{'='*70}\n")
        
        self._save_state()
        return True
    
    def is_session_complete(self) -> bool:
        """
        Check if current session has ended (with continuation possibility)
        
        Returns:
            True if session should end and break should start
        """
        
        if self.current_state != SessionState.ACTIVE_SESSION:
            return False
        
        elapsed = datetime.now() - self.session_start_time
        
        # Check if target actions reached
        if elapsed.total_seconds() >= self.session_duration_sec and self.actions_in_session >= self.session_action_target:
            # Maybe continue session instead of breaking
            if random.random() < self.session_continue_probability:
                # Extend session by 10-20 min
                extension = random.randint(600, 1200)
                self.session_duration_sec += extension
                self.session_action_target += random.randint(2, 4)
                self.session_continuation = True
                
                log.info(f"↩️  Continuing session (+{extension//60}m, new target: {self.session_action_target})")
                return False  # Don't end session yet
            else:
                return True  # End session
        
        return elapsed.total_seconds() >= self.session_duration_sec
    
    def end_session(self) -> dict:
        """
        End current session and start break
        
        Returns:
            Session summary dict
        """
        
        if self.current_state != SessionState.ACTIVE_SESSION:
            return {}
        
        elapsed = datetime.now() - self.session_start_time
        
        # Randomize break duration with extended breaks sometimes (20% chance for 2-4h)
        if random.random() < self.extended_break_probability:
            # Extended break (2-4 hours)
            self.break_duration_sec = random.randint(
                self.extended_break_min_hours * 3600,
                self.extended_break_max_hours * 3600
            )
            break_type = "EXTENDED"
        else:
            # Normal break (30-120 min)
            self.break_duration_sec = random.randint(
                self.break_duration_min * 60,
                self.break_duration_max * 60
            )
            break_type = "BREAK"
        
        self.break_start_time = datetime.now()
        self.current_state = SessionState.BREAK
        
        break_end = self.break_start_time + timedelta(seconds=self.break_duration_sec)
        
        summary = {
            "session_duration": elapsed.total_seconds(),
            "actions_performed": self.actions_in_session,
            "break_duration": self.break_duration_sec,
            "break_until": break_end,
        }
        
        log.info(f"\n{'='*70}")
        if break_type == "EXTENDED":
            log.info(f"⏸️  SESSION END - TAKING EXTENDED BREAK")
        else:
            log.info(f"⏸️  SESSION END - TAKING BREAK")
        log.info(f"   Session lasted: {elapsed.total_seconds()/60:.0f} min")
        log.info(f"   Actions performed: {self.actions_in_session}")
        log.info(f"   Break duration: {self.break_duration_sec/60:.0f} min")
        log.info(f"   Resume at: {break_end.strftime('%H:%M:%S')}")
        log.info(f"{'='*70}\n")
        
        self._save_state()
        return summary
    
    def is_in_break(self) -> bool:
        """
        Check if currently in break period
        
        Returns:
            True if in break period
        """
        
        if self.break_start_time is None:
            return False
        
        elapsed = datetime.now() - self.break_start_time
        return elapsed.total_seconds() < self.break_duration_sec
    
    def should_take_action(self) -> bool:
        """
        Check if enough time has passed since last action
        
        Natural pacing: 30 seconds to 3 minutes between actions
        With occasional browse-only periods (10-15% of session time)
        
        Returns:
            True if can take action now
        """
        
        # Sometimes just browse without action (human behavior)
        if random.random() < self.browse_only_probability:
            return False
        
        if self.last_action_time is None:
            return True
        
        elapsed = (datetime.now() - self.last_action_time).total_seconds()
        min_interval = self.min_action_interval_sec
        
        # Don't take action too soon
        if elapsed < min_interval:
            return False
        
        # Exponential distribution favoring longer waits (more realistic)
        # 60% chance within 30-60s, 30% chance 60-120s, 10% chance 120-180s
        roll = random.random()
        if elapsed < min_interval:  # 30s
            return False
        elif elapsed < min_interval + 30:  # 30-60s
            return roll < 0.6
        elif elapsed < min_interval * 2:  # 60-120s
            return roll < 0.9
        else:  # 120s+
            return True
    
    def record_action(self) -> None:
        """Record that action was taken"""
        
        self.last_action_time = datetime.now()
        self.actions_in_session += 1
    
    def get_session_info(self) -> dict:
        """
        Get information about current session
        
        Returns:
            Dict with session status
        """
        
        if self.current_state == SessionState.ACTIVE_SESSION and self.session_start_time:
            elapsed = datetime.now() - self.session_start_time
            remaining = self.session_duration_sec - elapsed.total_seconds()
            
            return {
                "state": self.current_state.value,
                "elapsed_sec": elapsed.total_seconds(),
                "remaining_sec": max(0, remaining),
                "percentage": min(100, int(100 * elapsed.total_seconds() / self.session_duration_sec)),
                "actions": self.actions_in_session,
                "target_actions": self.session_action_target,
            }
        
        elif self.current_state == SessionState.BREAK and self.break_start_time:
            elapsed = datetime.now() - self.break_start_time
            remaining = self.break_duration_sec - elapsed.total_seconds()
            
            return {
                "state": self.current_state.value,
                "elapsed_sec": elapsed.total_seconds(),
                "remaining_sec": max(0, remaining),
                "percentage": min(100, int(100 * elapsed.total_seconds() / self.break_duration_sec)),
            }
        
        return {
            "state": self.current_state.value,
        }
    
    def get_time_until_active(self) -> int:
        """Get seconds until next active window.

        Returns:
            Seconds to wait until active, or 0 if currently active.
        """

        now = datetime.now()

        # If we're currently in a break, return the remaining break time
        if self.current_state == SessionState.BREAK and self.break_start_time and self.break_duration_sec:
            elapsed = (now - self.break_start_time).total_seconds()
            remaining = self.break_duration_sec - elapsed
            return int(max(0, remaining))

        now_hour = now.hour

        # If currently in active hours
        if now_hour >= self.active_start_hour and now_hour < self.active_end_hour:
            return 0

        # Calculate time until next active window
        if now_hour >= self.active_end_hour:
            # After active hours - wait until tomorrow's start
            tomorrow_start = now + timedelta(days=1)
            tomorrow_start = tomorrow_start.replace(hour=self.active_start_hour, minute=0, second=0)
            wait_sec = (tomorrow_start - now).total_seconds()
        else:
            # Before active hours - wait until today's start
            today_start = now.replace(hour=self.active_start_hour, minute=0, second=0)
            wait_sec = (today_start - now).total_seconds()

        return int(max(0, wait_sec))
    
    def _save_state(self) -> None:
        """Save session state to disk for persistence"""
        
        try:
            state_data = {
                "state": self.current_state.value,
                "session_start": self.session_start_time.isoformat() if self.session_start_time else None,
                "session_duration": self.session_duration_sec,
                "session_action_target": self.session_action_target,
                "break_start": self.break_start_time.isoformat() if self.break_start_time else None,
                "break_duration": self.break_duration_sec,
                "actions_in_session": self.actions_in_session,
            }
            
            with open(self.state_file, "w") as f:
                import json
                json.dump(state_data, f, indent=2)
        
        except Exception as e:
            log.error(f"Failed to save session state: {e}")
    
    def _load_state(self) -> None:
        """Load session state from disk if exists"""
        
        if not self.state_file.exists():
            return
        
        try:
            import json
            with open(self.state_file, "r") as f:
                state_data = json.load(f)
            
            # Restore state
            if state_data.get("state"):
                self.current_state = SessionState(state_data["state"])
            
            if state_data.get("session_start"):
                self.session_start_time = datetime.fromisoformat(state_data["session_start"])
            
            if state_data.get("session_duration"):
                self.session_duration_sec = state_data["session_duration"]
            
            if state_data.get("break_start"):
                self.break_start_time = datetime.fromisoformat(state_data["break_start"])
            
            if state_data.get("break_duration"):
                self.break_duration_sec = state_data["break_duration"]
            
            if state_data.get("actions_in_session"):
                self.actions_in_session = state_data["actions_in_session"]
            
            if state_data.get("session_action_target"):
                self.session_action_target = state_data["session_action_target"]
            
            # If the restored session is already complete or too old, reset to idle
            if self.current_state == SessionState.ACTIVE_SESSION and self.session_start_time:
                now = datetime.now()
                session_end = self.session_start_time + timedelta(seconds=self.session_duration_sec or 0)

                # If the session end time has passed, or the session is older than 12h, reset
                if now > session_end or now - self.session_start_time > timedelta(hours=12):
                    log.info("⚠️ Restored session is stale/complete, resetting to idle")
                    self.current_state = SessionState.IDLE
                    self.session_start_time = None
                    self.session_duration_sec = None
                    self.session_action_target = None
                    self.actions_in_session = 0

            # If we restored an active session without a target, recalc it
            if (self.current_state == SessionState.ACTIVE_SESSION and 
                self.session_duration_sec and 
                self.session_action_target is None):
                session_minutes = self.session_duration_sec / 60
                self.session_action_target = max(2, int(session_minutes / 5))
                log.info(f"✓ Recalculated session target actions: {self.session_action_target}")

            log.info(f"✓ Restored session state from disk: {self.current_state.value}")

        except Exception as e:
            log.error(f"Failed to load session state: {e}")

    def print_status(self) -> None:
        """Print human-readable status."""

        info = self.get_session_info()
        state = SessionState(info.get("state"))

        if state == SessionState.ACTIVE_SESSION:
            elapsed = info.get("elapsed_sec", 0)
            remaining = info.get("remaining_sec", 0)
            actions = info.get("actions", 0)
            target = info.get("target_actions", 0)
            pct = info.get("percentage", 0)

            log.info(f"📱 SESSION: {elapsed/60:.0f}m elapsed, {remaining/60:.0f}m remaining ({pct}%)")
            log.info(f"   Actions: {actions}/{target}")

        elif state == SessionState.BREAK:
            elapsed = info.get("elapsed_sec", 0)
            remaining = info.get("remaining_sec", 0)
            pct = info.get("percentage", 0)

            log.info(f"⏸️  BREAK: {elapsed/60:.0f}m elapsed, {remaining/60:.0f}m remaining ({pct}%)")

        elif state == SessionState.OUTSIDE_HOURS:
            wait_sec = self.get_time_until_active()
            log.info(f"😴 OUTSIDE ACTIVE HOURS - sleeping for {wait_sec/3600:.1f} hours")

        else:
            log.info(f"🔄 IDLE - waiting to start session")


# Global instance
_session_manager: SessionManager = None


def init_session_manager(config) -> SessionManager:
    """Initialize global session manager"""
    global _session_manager
    _session_manager = SessionManager(config)
    return _session_manager


def get_session_manager() -> SessionManager:
    """Get global session manager instance"""
    global _session_manager
    if _session_manager is None:
        raise RuntimeError("Session manager not initialized. Call init_session_manager() first.")
    return _session_manager
