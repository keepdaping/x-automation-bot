"""Core error handling and recovery system."""

import time
import traceback
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from logger_setup import log


class ErrorSeverity(Enum):
    RECOVERABLE = "recoverable"
    BROWSER_ERROR = "browser_error"
    DETECTION = "detection"
    FATAL = "fatal"


class ErrorHandler:
    def __init__(self, config, browser_manager=None):
        self.config = config
        self.browser_manager = browser_manager
        self.consecutive_errors = 0
        self.max_consecutive_errors = 5
        self.last_error_time = None
        self.detection_cooldown_start = None
        self.max_backoff_seconds = 300
        self.detection_cooldown_hours = 24
        self.error_log = Path("data/error_history.log")
        self.error_log.parent.mkdir(exist_ok=True)
        self.cooldown_file = Path("data/detection_cooldown.txt")
        self._load_detection_cooldown()

    def _load_detection_cooldown(self):
        if self.cooldown_file.exists():
            try:
                with open(self.cooldown_file, "r") as f:
                    ts = f.read().strip()
                    if ts:
                        self.detection_cooldown_start = datetime.fromisoformat(ts)
                        log.warning(f"⏸️  Loaded detection cooldown: {self.detection_cooldown_start}")
            except Exception:
                pass

    def handle_error(self, error: Exception, context: str = "unknown") -> tuple:
        self._log_error(error, context)
        severity = self._classify_error(error)
        if severity == ErrorSeverity.FATAL:
            log.critical(f"💥 FATAL in {context}: {error}")
            return False, 0
        elif severity == ErrorSeverity.DETECTION:
            log.critical(f"⚠️  BOT DETECTION in {context}")
            self.detection_cooldown_start = datetime.now()
            try:
                with open(self.cooldown_file, "w") as f:
                    f.write(self.detection_cooldown_start.isoformat())
            except Exception:
                pass
            return False, self.detection_cooldown_hours * 3600
        elif severity == ErrorSeverity.BROWSER_ERROR:
            if self.browser_manager:
                try:
                    self.browser_manager.restart()
                    self.consecutive_errors = 0
                    return True, 5
                except Exception:
                    return False, 0
            return False, 0
        else:
            self.consecutive_errors += 1
            import random
            wait = min(2 ** self.consecutive_errors - 1, self.max_backoff_seconds)
            wait = int(wait * random.uniform(0.75, 1.25))
            if self.consecutive_errors >= self.max_consecutive_errors:
                return False, 0
            return True, wait

    def _classify_error(self, error: Exception) -> ErrorSeverity:
        msg = str(error).lower()
        if any(x in msg for x in ["detected", "blocked", "403", "401"]):
            return ErrorSeverity.DETECTION
        if any(x in msg for x in ["browser", "chromium", "playwright"]):
            return ErrorSeverity.BROWSER_ERROR
        if "authentication" in msg and ("invalid" in msg or "expired" in msg):
            return ErrorSeverity.FATAL
        return ErrorSeverity.RECOVERABLE

    def reset_error_counter(self):
        self.consecutive_errors = 0

    def is_in_detection_cooldown(self) -> bool:
        if self.detection_cooldown_start is None:
            return False
        elapsed = datetime.now() - self.detection_cooldown_start
        if elapsed >= timedelta(hours=self.detection_cooldown_hours):
            self.detection_cooldown_start = None
            try:
                self.cooldown_file.unlink(missing_ok=True)
            except Exception:
                pass
            return False
        return True

    def _log_error(self, error: Exception, context: str):
        try:
            with open(self.error_log, "a") as f:
                f.write(f"\n{'='*50}\n{datetime.now().isoformat()} | {context}\n{type(error).__name__}: {error}\n{traceback.format_exc()}\n")
        except Exception:
            pass


_error_handler: ErrorHandler = None

def init_error_handler(config, browser_manager=None) -> ErrorHandler:
    global _error_handler
    _error_handler = ErrorHandler(config, browser_manager)
    return _error_handler

def get_error_handler() -> ErrorHandler:
    global _error_handler
    if _error_handler is None:
        raise RuntimeError("Error handler not initialized")
    return _error_handler
