import json
import time
from pathlib import Path
from datetime import datetime
from logger_setup import log


LOG_FILE = Path("data/engagement_log.json")


def log_result(tweet_text, action, metrics):
    """Log action result"""
    if LOG_FILE.exists():
        data = json.loads(LOG_FILE.read_text())
    else:
        data = []

    data.append({
        "timestamp": datetime.now().isoformat(),
        "tweet": tweet_text,
        "action": action,
        "metrics": metrics
    })

    LOG_FILE.write_text(json.dumps(data, indent=2))


class PerformanceTracker:
    """Track bot health and performance metrics"""
    
    def __init__(self):
        self.cycle_count = 0
        self.success_count = 0
        self.error_count = 0
        self.start_time = time.time()
        
        # Daily limits tracking
        self.likes_today = 0
        self.replies_today = 0
        self.follows_today = 0
        self.like_limit = 10
        self.reply_limit = 5
        self.follow_limit = 8
        
        # Performance metrics
        self.consecutive_errors = 0
        self.max_consecutive_errors = 5
    
    def record_cycle(self, success=True, action_count=0):
        """Record a completed cycle"""
        self.cycle_count += 1
        
        if success:
            self.success_count += 1
            self.consecutive_errors = 0
        else:
            self.error_count += 1
            self.consecutive_errors += 1
            log.warning(f"Consecutive errors: {self.consecutive_errors}/{self.max_consecutive_errors}")
            
            if self.consecutive_errors >= self.max_consecutive_errors:
                log.error("MAX consecutive errors reached!")
    
    def record_action(self, action_type):
        """Record a performed action"""
        action_type = action_type.lower()
        if action_type == "like":
            self.likes_today += 1
        elif action_type == "reply":
            self.replies_today += 1
        elif action_type == "follow":
            self.follows_today += 1
    
    def can_perform_action(self, action_type):
        """Check if action limit not exceeded"""
        action_type = action_type.lower()
        if action_type == "like":
            return self.likes_today < self.like_limit
        elif action_type == "reply":
            return self.replies_today < self.reply_limit
        elif action_type == "follow":
            return self.follows_today < self.follow_limit
        return True
    
    def get_recommended_sleep(self):
        """Get recommended sleep time between cycles"""
        base_sleep = 120
        if self.consecutive_errors > 0:
            base_sleep += (self.consecutive_errors * 60)
        return base_sleep + (time.time() % 60)  # Add randomization
    
    def get_uptime(self):
        """Get bot uptime in seconds"""
        return time.time() - self.start_time
    
    def get_success_rate(self):
        """Get cycle success rate"""
        if self.cycle_count == 0:
            return 0
        return (self.success_count / self.cycle_count) * 100
    
    def print_summary(self):
        """Print bot health summary"""
        uptime_hours = self.get_uptime() / 3600
        success_rate = self.get_success_rate()
        
        log.info("\n" + "="*70)
        log.info("BOT PERFORMANCE SUMMARY")
        log.info("="*70)
        log.info(f"Uptime: {uptime_hours:.2f} hours")
        log.info(f"Total Cycles: {self.cycle_count}")
        log.info(f"Successful: {self.success_count}")
        log.info(f"Failed: {self.error_count}")
        log.info(f"Success Rate: {success_rate:.1f}%")
        log.info(f"Actions Performed:")
        log.info(f"  Likes: {self.likes_today}/{self.like_limit}")
        log.info(f"  Replies: {self.replies_today}/{self.reply_limit}")
        log.info(f"  Follows: {self.follows_today}/{self.follow_limit}")
        log.info("="*70)
    
    def export_metrics(self, filename="bot_metrics.json"):
        """Export metrics to JSON file"""
        metrics = {
            "timestamp": datetime.now().isoformat(),
            "uptime_seconds": self.get_uptime(),
            "total_cycles": self.cycle_count,
            "successful_cycles": self.success_count,
            "failed_cycles": self.error_count,
            "success_rate_percent": self.get_success_rate(),
            "likes_today": self.likes_today,
            "replies_today": self.replies_today,
            "follows_today": self.follows_today,
        }
        
        try:
            with open(filename, "w") as f:
                json.dump(metrics, f, indent=2)
            log.info(f"Metrics exported to {filename}")
        except Exception as e:
            log.error(f"Failed to export metrics: {e}")
