"""
Human-like session behavior manager.
Unchanged from original - well-designed.
"""

import random
import time
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional
from pathlib import Path
from logger_setup import log


class SessionState(Enum):
    IDLE = "idle"
    ACTIVE_SESSION = "active"
    BREAK = "break"
    OUTSIDE_HOURS = "outside_hours"


class SessionManager:
    def __init__(self, config):
        self.config = config
        self.session_duration_min = getattr(config, "SESSION_DURATION_MIN", 20)
        self.session_duration_max = getattr(config, "SESSION_DURATION_MAX", 45)
        self.break_duration_min = getattr(config, "BREAK_DURATION_MIN", 30)
        self.break_duration_max = getattr(config, "BREAK_DURATION_MAX", 120)
        self.active_start_hour = getattr(config, "ACTIVE_START_HOUR", 8)
        self.active_end_hour = getattr(config, "ACTIVE_END_HOUR", 23)
        self.min_action_interval_sec = getattr(config, "MIN_ACTION_INTERVAL_SEC", 30)
        self.max_action_interval_sec = getattr(config, "MAX_ACTION_INTERVAL_SEC", 180)
        self.session_continue_probability = getattr(config, "SESSION_CONTINUE_PROBABILITY", 0.40)
        self.extended_break_probability = getattr(config, "SESSION_EXTENDED_BREAK_PROBABILITY", 0.0)
        self.extended_break_min_hours = getattr(config, "SESSION_EXTENDED_BREAK_MIN_HOURS", 2)
        self.extended_break_max_hours = getattr(config, "SESSION_EXTENDED_BREAK_MAX_HOURS", 4)
        self.first_action_delay_min = getattr(config, "FIRST_ACTION_DELAY_SEC_MIN", 30)
        self.first_action_delay_max = getattr(config, "FIRST_ACTION_DELAY_SEC_MAX", 120)
        self.browse_only_probability = getattr(config, "SESSION_BROWSE_ONLY_PROBABILITY", 0.05)

        self.current_state = SessionState.IDLE
        self.session_start_time: Optional[datetime] = None
        self.session_duration_sec: Optional[int] = None
        self.break_start_time: Optional[datetime] = None
        self.break_duration_sec: Optional[int] = None
        self.last_action_time: Optional[datetime] = None
        self.actions_in_session = 0
        self.session_action_target: Optional[int] = None

        self.state_file = Path("data/session_state.txt")
        self.state_file.parent.mkdir(exist_ok=True)
        self._load_state()

        log.info(f"✓ Session Manager: {self.active_start_hour}:00-{self.active_end_hour}:00, {self.session_duration_min}-{self.session_duration_max}min sessions")

    def should_be_active(self) -> bool:
        now_hour = datetime.now().hour
        if now_hour < self.active_start_hour or now_hour >= self.active_end_hour:
            self.current_state = SessionState.OUTSIDE_HOURS
            return False
        if self.is_in_break():
            self.current_state = SessionState.BREAK
            return False
        return True

    def start_session(self) -> bool:
        if self.current_state == SessionState.ACTIVE_SESSION:
            return False
        self.session_duration_sec = random.randint(self.session_duration_min * 60, self.session_duration_max * 60)
        self.session_start_time = datetime.now()
        self.actions_in_session = 0
        first_action_delay = random.randint(self.first_action_delay_min, self.first_action_delay_max)
        self.last_action_time = self.session_start_time - timedelta(seconds=first_action_delay)
        self.session_action_target = random.randint(8, 12)
        self.current_state = SessionState.ACTIVE_SESSION
        session_end = self.session_start_time + timedelta(seconds=self.session_duration_sec)
        log.info(f"\n📱 SESSION START | {self.session_duration_sec//60}min | target: {self.session_action_target} actions | until: {session_end.strftime('%H:%M:%S')}\n")
        self._save_state()
        return True

    def is_session_complete(self) -> bool:
        if self.current_state != SessionState.ACTIVE_SESSION:
            return False
        elapsed = datetime.now() - self.session_start_time
        if elapsed.total_seconds() >= self.session_duration_sec and self.actions_in_session >= self.session_action_target:
            if random.random() < self.session_continue_probability:
                extension = random.randint(600, 1200)
                self.session_duration_sec += extension
                self.session_action_target += random.randint(2, 4)
                log.info(f"↩️  Extending session +{extension//60}m")
                return False
            return True
        return elapsed.total_seconds() >= self.session_duration_sec

    def end_session(self) -> dict:
        if self.current_state != SessionState.ACTIVE_SESSION:
            return {}
        elapsed = datetime.now() - self.session_start_time
        if random.random() < self.extended_break_probability:
            self.break_duration_sec = random.randint(self.extended_break_min_hours * 3600, self.extended_break_max_hours * 3600)
            break_type = "EXTENDED"
        else:
            self.break_duration_sec = random.randint(self.break_duration_min * 60, self.break_duration_max * 60)
            break_type = "NORMAL"
        self.break_start_time = datetime.now()
        self.current_state = SessionState.BREAK
        break_end = self.break_start_time + timedelta(seconds=self.break_duration_sec)
        log.info(f"\n⏸️  SESSION END | {elapsed.total_seconds()//60:.0f}min | {self.actions_in_session} actions | {break_type} break {self.break_duration_sec//60:.0f}min | resume: {break_end.strftime('%H:%M:%S')}\n")
        self._save_state()
        return {"session_duration": elapsed.total_seconds(), "actions": self.actions_in_session, "break_duration": self.break_duration_sec}

    def is_in_break(self) -> bool:
        if self.break_start_time is None:
            return False
        elapsed = datetime.now() - self.break_start_time
        return elapsed.total_seconds() < self.break_duration_sec

    def should_take_action(self) -> bool:
        if random.random() < self.browse_only_probability:
            return False
        if self.last_action_time is None:
            return True
        elapsed = (datetime.now() - self.last_action_time).total_seconds()
        if elapsed < self.min_action_interval_sec:
            return False
        roll = random.random()
        if elapsed < self.min_action_interval_sec + 30:
            return roll < 0.6
        elif elapsed < self.min_action_interval_sec * 2:
            return roll < 0.9
        return True

    def record_action(self) -> None:
        self.last_action_time = datetime.now()
        self.actions_in_session += 1

    def get_session_info(self) -> dict:
        if self.current_state == SessionState.ACTIVE_SESSION and self.session_start_time:
            elapsed = datetime.now() - self.session_start_time
            remaining = self.session_duration_sec - elapsed.total_seconds()
            return {"state": self.current_state.value, "elapsed_sec": elapsed.total_seconds(), "remaining_sec": max(0, remaining),
                    "percentage": min(100, int(100 * elapsed.total_seconds() / self.session_duration_sec)),
                    "actions": self.actions_in_session, "target_actions": self.session_action_target}
        elif self.current_state == SessionState.BREAK and self.break_start_time:
            elapsed = datetime.now() - self.break_start_time
            return {"state": self.current_state.value, "elapsed_sec": elapsed.total_seconds(),
                    "remaining_sec": max(0, self.break_duration_sec - elapsed.total_seconds()),
                    "percentage": min(100, int(100 * elapsed.total_seconds() / self.break_duration_sec))}
        return {"state": self.current_state.value}

    def get_time_until_active(self) -> int:
        now = datetime.now()
        if self.current_state == SessionState.BREAK and self.break_start_time and self.break_duration_sec:
            elapsed = (now - self.break_start_time).total_seconds()
            return int(max(0, self.break_duration_sec - elapsed))
        now_hour = now.hour
        if self.active_start_hour <= now_hour < self.active_end_hour:
            return 0
        if now_hour >= self.active_end_hour:
            tomorrow_start = now + timedelta(days=1)
            tomorrow_start = tomorrow_start.replace(hour=self.active_start_hour, minute=0, second=0)
            return int((tomorrow_start - now).total_seconds())
        today_start = now.replace(hour=self.active_start_hour, minute=0, second=0)
        return int(max(0, (today_start - now).total_seconds()))

    def print_status(self) -> None:
        info = self.get_session_info()
        state = info.get("state")
        if state == "active":
            log.info(f"📱 SESSION: {info.get('elapsed_sec',0)/60:.0f}m, {info.get('actions',0)}/{info.get('target_actions',0)} actions")
        elif state == "break":
            log.info(f"⏸️  BREAK: {info.get('remaining_sec',0)/60:.0f}m remaining")
        elif state == "outside_hours":
            log.info(f"😴 OUTSIDE HOURS - {self.get_time_until_active()/3600:.1f}h until active")
        else:
            log.info("🔄 IDLE")

    def _save_state(self) -> None:
        try:
            import json
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
                json.dump(state_data, f, indent=2)
        except Exception as e:
            log.error(f"Failed to save session state: {e}")

    def _load_state(self) -> None:
        if not self.state_file.exists():
            return
        try:
            import json
            with open(self.state_file, "r") as f:
                data = json.load(f)
            if data.get("state"):
                self.current_state = SessionState(data["state"])
            if data.get("session_start"):
                self.session_start_time = datetime.fromisoformat(data["session_start"])
            self.session_duration_sec = data.get("session_duration")
            self.session_action_target = data.get("session_action_target")
            if data.get("break_start"):
                self.break_start_time = datetime.fromisoformat(data["break_start"])
            self.break_duration_sec = data.get("break_duration")
            self.actions_in_session = data.get("actions_in_session", 0)

            # Reset stale sessions
            if self.current_state == SessionState.ACTIVE_SESSION and self.session_start_time:
                now = datetime.now()
                session_end = self.session_start_time + timedelta(seconds=self.session_duration_sec or 0)
                if now > session_end or now - self.session_start_time > timedelta(hours=12):
                    self.current_state = SessionState.IDLE
                    self.session_start_time = None
                    self.session_duration_sec = None
                    self.actions_in_session = 0
            if self.current_state == SessionState.ACTIVE_SESSION and self.session_duration_sec and not self.session_action_target:
                self.session_action_target = random.randint(8, 12)
            log.info(f"✓ Restored session state: {self.current_state.value}")
        except Exception as e:
            log.error(f"Failed to load session state: {e}")


_session_manager: SessionManager = None

def init_session_manager(config) -> SessionManager:
    global _session_manager
    _session_manager = SessionManager(config)
    return _session_manager

def get_session_manager() -> SessionManager:
    global _session_manager
    if _session_manager is None:
        raise RuntimeError("Session manager not initialized")
    return _session_manager
