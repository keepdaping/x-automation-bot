"""
Core error handling and recovery system.

Handles:
- Recoverable errors (network, timeouts) with exponential backoff
- Browser state errors with automatic restart
- Bot detection with extended cooldown
- Fatal errors that require manual intervention
"""

import time
import traceback
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional, Callable
from pathlib import Path
from logger_setup import log


class ErrorSeverity(Enum):
    """Error severity levels"""
    RECOVERABLE = "recoverable"      # Retry with backoff
    BROWSER_ERROR = "browser_error"  # Restart browser
    DETECTION = "detection"           # Extended cooldown
    FATAL = "fatal"                   # Stop bot


class ErrorHandler:
    """Handle errors with appropriate recovery strategies"""
    
    def __init__(self, config, browser_manager=None):
        """
        Initialize error handler
        
        Args:
            config: Config object
            browser_manager: BrowserManager instance for recovery
        """
        self.config = config
        self.browser_manager = browser_manager
        
        # Error tracking
        self.consecutive_errors = 0
        self.max_consecutive_errors = 5
        self.last_error_time = None
        self.detection_cooldown_start = None
        
        # Recovery configuration
        self.max_backoff_seconds = 300  # Max 5 minute wait
        self.detection_cooldown_hours = 24
        
        # Error history file
        self.error_log = Path("data/error_history.log")
        self.error_log.parent.mkdir(exist_ok=True)
        
        # Detection cooldown persistence file
        self.cooldown_file = Path("data/detection_cooldown.txt")
        
        # Load cooldown from disk if it exists
        self._load_detection_cooldown()
    
    def _load_detection_cooldown(self):
        """Load detection cooldown from disk on startup"""
        if self.cooldown_file.exists():
            try:
                with open(self.cooldown_file, "r") as f:
                    timestamp_str = f.read().strip()
                    if timestamp_str:
                        self.detection_cooldown_start = datetime.fromisoformat(timestamp_str)
                        log.warning(f"⏸️  Loaded detection cooldown from disk: {self.detection_cooldown_start}")
            except Exception as e:
                log.error(f"Failed to load detection cooldown: {e}")
    
    def _save_detection_cooldown(self):
        """Save detection cooldown to disk for persistence"""
        try:
            with open(self.cooldown_file, "w") as f:
                f.write(self.detection_cooldown_start.isoformat())
            log.info(f"✓ Detection cooldown saved to disk until {self.detection_cooldown_start}")
        except Exception as e:
            log.error(f"Failed to save detection cooldown: {e}")
    
    def _clear_detection_cooldown(self):
        """Clear detection cooldown from disk"""
        try:
            if self.cooldown_file.exists():
                self.cooldown_file.unlink()
                log.info("✓ Detection cooldown cleared from disk")
        except Exception as e:
            log.error(f"Failed to clear detection cooldown: {e}")
    
    
    def handle_error(self, error: Exception, context: str = "unknown") -> tuple:
        """
        Handle an error with appropriate recovery
        
        Args:
            error: The exception that occurred
            context: What was the bot doing when error occurred
            
        Returns:
            (should_retry: bool, wait_seconds: int)
            - should_retry: Whether to retry the action
            - wait_seconds: How long to wait before retry (0 if no wait)
        """
        
        # Log error details
        self._log_error(error, context)
        
        # Determine severity
        severity = self._classify_error(error)
        
        if severity == ErrorSeverity.FATAL:
            return self._handle_fatal_error(error, context)
        
        elif severity == ErrorSeverity.DETECTION:
            return self._handle_detection_error(error, context)
        
        elif severity == ErrorSeverity.BROWSER_ERROR:
            return self._handle_browser_error(error, context)
        
        elif severity == ErrorSeverity.RECOVERABLE:
            return self._handle_recoverable_error(error, context)
        
        else:
            # Unknown: treat as recoverable
            return self._handle_recoverable_error(error, context)
    
    def _classify_error(self, error: Exception) -> ErrorSeverity:
        """Classify error by type"""
        
        error_type = type(error).__name__
        error_msg = str(error).lower()
        
        # Detection errors
        if any(x in error_msg for x in ["detected", "blocked", "unauthorized", "403", "401"]):
            return ErrorSeverity.DETECTION
        
        # Browser errors
        if any(x in error_msg for x in ["browser", "chromium", "page", "playwright"]):
            return ErrorSeverity.BROWSER_ERROR
        
        # Fatal authentication errors
        if "authentication" in error_msg or "session" in error_msg.lower():
            if "invalid" in error_msg or "expired" in error_msg:
                return ErrorSeverity.FATAL
        
        # Recoverable: network, timeout, connection
        if any(x in error_type for x in ["Connection", "Timeout", "Network"]):
            return ErrorSeverity.RECOVERABLE
        
        # Playwright timeout is recoverable
        if "TimeoutError" in error_type:
            return ErrorSeverity.RECOVERABLE
        
        # Default to recoverable
        return ErrorSeverity.RECOVERABLE
    
    def _handle_recoverable_error(self, error: Exception, context: str) -> tuple:
        """
        Handle recoverable errors with exponential backoff
        
        Returns:
            (should_retry, wait_seconds)
        """
        
        self.consecutive_errors += 1
        
        # Calculate exponential backoff
        wait_seconds = min(2 ** self.consecutive_errors - 1, self.max_backoff_seconds)
        
        # Add randomness (±25%)
        import random
        randomization = random.uniform(0.75, 1.25)
        wait_seconds = int(wait_seconds * randomization)
        
        log.warning(
            f"Recoverable error in {context} (attempt {self.consecutive_errors}/"
            f"{self.max_consecutive_errors}). Waiting {wait_seconds}s: {type(error).__name__}"
        )
        
        # Check if too many consecutive errors
        if self.consecutive_errors >= self.max_consecutive_errors:
            log.critical(f"Max consecutive errors reached ({self.max_consecutive_errors})")
            return False, 0  # Don't retry
        
        return True, wait_seconds
    
    def _handle_browser_error(self, error: Exception, context: str) -> tuple:
        """
        Handle browser errors by restarting browser
        
        Returns:
            (should_retry, wait_seconds)
        """
        
        log.error(f"Browser error in {context}: {error}")
        
        if self.browser_manager is None:
            log.error("Browser manager not available for recovery")
            return False, 0
        
        try:
            log.info("Attempting browser restart...")
            self.browser_manager.restart()
            
            # Reset error counter on successful restart
            self.consecutive_errors = 0
            log.info("✓ Browser restarted successfully")
            
            return True, 5  # Wait 5 seconds for browser to stabilize
            
        except Exception as restart_error:
            log.error(f"Browser restart failed: {restart_error}")
            return False, 0  # Can't recover
    
    def _handle_detection_error(self, error: Exception, context: str) -> tuple:
        """
        Handle bot detection with extended cooldown
        
        Returns:
            (should_retry, wait_seconds)
        """
        
        log.critical(f"⚠️  BOT DETECTION: X detected automated access in {context}")
        log.critical(f"Error: {error}")
        
        # Set cooldown period
        self.detection_cooldown_start = datetime.now()
        cooldown_until = self.detection_cooldown_start + timedelta(hours=self.detection_cooldown_hours)
        
        log.critical(f"⏸️  COOLDOWN ACTIVE until {cooldown_until.strftime('%Y-%m-%d %H:%M:%S')}")
        log.critical(f"Do not run bot during this period - will get permanently banned")
        
        # PERSIST cooldown to disk so it survives restarts
        self._save_detection_cooldown()
        
        # Save detection event
        self._save_detection_event(error, context)
        
        # Wait full cooldown before retrying
        wait_seconds = self.detection_cooldown_hours * 3600
        
        return False, wait_seconds  # Don't retry yet
    
    def _handle_fatal_error(self, error: Exception, context: str) -> tuple:
        """
        Handle fatal errors that require manual intervention
        
        Returns:
            (should_retry, wait_seconds)
        """
        
        log.critical(f"💥 FATAL ERROR in {context}")
        log.critical(f"Error: {error}")
        log.critical(f"Manual intervention required!")
        
        # Save fatal event
        self._save_fatal_event(error, context)
        
        return False, 0  # Don't retry
    
    def reset_error_counter(self):
        """Reset consecutive error counter on successful action"""
        
        if self.consecutive_errors > 0:
            log.debug(f"Action succeeded, resetting error counter ({self.consecutive_errors} → 0)")
        
        self.consecutive_errors = 0
        self.last_error_time = None
    
    def is_in_detection_cooldown(self) -> bool:
        """Check if currently under detection cooldown"""
        
        if self.detection_cooldown_start is None:
            return False
        
        elapsed = datetime.now() - self.detection_cooldown_start
        cooldown_duration = timedelta(hours=self.detection_cooldown_hours)
        
        if elapsed >= cooldown_duration:
            log.info("✓ Detection cooldown period expired, resuming bot")
            self.detection_cooldown_start = None
            self._clear_detection_cooldown()  # Clear from disk too
            return False
        
        remaining = cooldown_duration - elapsed
        log.warning(f"⏸️  Still in detection cooldown ({remaining.total_seconds() / 3600:.1f}h remaining)")
        
        return True
    
    def _log_error(self, error: Exception, context: str):
        """Log error details to file"""
        
        try:
            with open(self.error_log, "a") as f:
                f.write(f"\n{'='*70}\n")
                f.write(f"Timestamp: {datetime.now().isoformat()}\n")
                f.write(f"Context: {context}\n")
                f.write(f"Error Type: {type(error).__name__}\n")
                f.write(f"Error: {str(error)}\n")
                f.write(f"Traceback:\n{traceback.format_exc()}\n")
        except Exception as e:
            log.error(f"Failed to log error: {e}")
    
    def _save_detection_event(self, error: Exception, context: str):
        """Save detection event details"""
        
        detection_file = Path("data/detection_events.log")
        
        try:
            with open(detection_file, "a") as f:
                f.write(f"{datetime.now().isoformat()} | {context} | {str(error)}\n")
        except Exception as e:
            log.error(f"Failed to save detection event: {e}")
    
    def _save_fatal_event(self, error: Exception, context: str):
        """Save fatal error event details"""
        
        fatal_file = Path("data/fatal_errors.log")
        
        try:
            with open(fatal_file, "a") as f:
                f.write(f"\n{'='*70}\n")
                f.write(f"Timestamp: {datetime.now().isoformat()}\n")
                f.write(f"Context: {context}\n")
                f.write(f"Error: {type(error).__name__}: {str(error)}\n")
                f.write(f"Traceback:\n{traceback.format_exc()}\n")
        except Exception as e:
            log.error(f"Failed to save fatal event: {e}")
    
    def export_error_stats(self) -> dict:
        """Export error statistics"""
        
        return {
            "consecutive_errors": self.consecutive_errors,
            "max_consecutive": self.max_consecutive_errors,
            "in_detection_cooldown": self.is_in_detection_cooldown(),
            "cooldown_started": self.detection_cooldown_start.isoformat() if self.detection_cooldown_start else None,
        }


# Global instance
_error_handler: ErrorHandler = None


def init_error_handler(config, browser_manager=None) -> ErrorHandler:
    """Initialize global error handler"""
    global _error_handler
    _error_handler = ErrorHandler(config, browser_manager)
    return _error_handler


def get_error_handler() -> ErrorHandler:
    """Get global error handler instance"""
    global _error_handler
    if _error_handler is None:
        raise RuntimeError("Error handler not initialized. Call init_error_handler() first.")
    return _error_handler
