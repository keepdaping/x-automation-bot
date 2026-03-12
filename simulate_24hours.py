"""
24-hour behavioral simulation of the bot with detailed timeline analysis.

This script simulates the bot running for an entire day to identify:
1. Session timing patterns
2. Action frequency consistency
3. Rate limiter triggers
4. Cluster detection triggers
5. Break timing patterns
6. Active hour enforcement
7. Error recovery scenarios

Output: Detailed minute-by-minute timeline + pattern analysis
"""

import random
import time
import sys
from datetime import datetime, timedelta, time as dt_time
from enum import Enum
from pathlib import Path
from typing import List, Dict, Tuple

# Fix Unicode output on Windows
if sys.stdout.encoding != 'utf-8':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Suppress actual logging to capture only simulation output
import logging
logging.getLogger().setLevel(logging.CRITICAL)


class SimulationEvent:
    """Single event in 24-hour simulation"""
    def __init__(self, sim_time: datetime, event_type: str, description: str, details: dict = None):
        self.sim_time = sim_time
        self.event_type = event_type  # session_start, action, rate_limit, cluster, error, etc.
        self.description = description
        self.details = details or {}


class BotSimulator:
    """Simulates bot behavior for 24 hours"""
    
    def __init__(self):
        # Config values (from config.py)
        self.SESSION_DURATION_MIN = 20
        self.SESSION_DURATION_MAX = 45
        self.BREAK_DURATION_MIN = 30
        self.BREAK_DURATION_MAX = 120
        self.ACTIVE_START_HOUR = 8
        self.ACTIVE_END_HOUR = 23
        self.MIN_ACTION_INTERVAL_SEC = 30
        self.MAX_ACTION_INTERVAL_SEC = 180
        
        # Rate limiter config
        self.DAILY_LIMIT_LIKE = 60
        self.DAILY_LIMIT_REPLY = 5
        self.DAILY_LIMIT_FOLLOW = 3
        
        # Hourly limits (computed with math.ceil for proper distribution)
        import math
        self.HOURLY_LIMIT_LIKE = max(1, math.ceil(self.DAILY_LIMIT_LIKE / 12))
        self.HOURLY_LIMIT_REPLY = max(1, math.ceil(self.DAILY_LIMIT_REPLY / 12))
        self.HOURLY_LIMIT_FOLLOW = max(1, math.ceil(self.DAILY_LIMIT_FOLLOW / 12))
        
        # Cluster detection
        self.CLUSTER_THRESHOLD_ACTIONS = 8
        self.CLUSTER_THRESHOLD_MINUTES = 10
        
        # Simulation tracking
        self.events: List[SimulationEvent] = []
        self.sim_time = None  # Current simulation time
        self.start_time = None  # Simulation start time
        
        # Session state
        self.session_active = False
        self.session_start_time = None
        self.session_duration = None
        self.session_actions = 0
        self.session_target_actions = 0
        
        # Break state
        self.break_active = False
        self.break_start_time = None
        self.break_duration = None
        
        # Action tracking (per hour)
        self.actions_by_hour: Dict[str, Dict[str, int]] = {}  # hour -> {like, reply, follow}
        self.actions_by_day: Dict[str, int] = {
            "like": 0,
            "reply": 0,
            "follow": 0,
        }
        
        # Recent actions for cluster detection
        self.recent_actions: List[Tuple[str, datetime]] = []  # (action_type, time)
        
        # Last action time
        self.last_action_time = None
        
        # Error tracking
        self.consecutive_errors = 0
        self.error_cooldown_active = False
        self.error_cooldown_until = None
    
    def log_event(self, event_type: str, description: str, details: dict = None):
        """Log a simulation event"""
        event = SimulationEvent(self.sim_time, event_type, description, details)
        self.events.append(event)
    
    def should_be_active(self) -> bool:
        """Check if bot should be active at current sim_time"""
        hour = self.sim_time.hour
        is_within_active_hours = hour >= self.ACTIVE_START_HOUR and hour < self.ACTIVE_END_HOUR
        
        if not is_within_active_hours:
            return False
        
        if self.break_active:
            return False
        
        return True
    
    def get_time_until_active(self) -> int:
        """Get seconds until next active window"""
        hour = self.sim_time.hour
        
        if hour >= self.ACTIVE_START_HOUR and hour < self.ACTIVE_END_HOUR:
            return 0
        
        if hour >= self.ACTIVE_END_HOUR:
            # After active hours - wait until tomorrow
            tomorrow_start = self.sim_time + timedelta(days=1)
            tomorrow_start = tomorrow_start.replace(hour=self.ACTIVE_START_HOUR, minute=0, second=0)
            return int((tomorrow_start - self.sim_time).total_seconds())
        else:
            # Before active hours - wait until today
            today_start = self.sim_time.replace(hour=self.ACTIVE_START_HOUR, minute=0, second=0)
            return int((today_start - self.sim_time).total_seconds())
    
    def start_session(self):
        """Start a new session"""
        self.session_active = True
        self.session_start_time = self.sim_time
        self.session_duration = random.randint(self.SESSION_DURATION_MIN * 60, self.SESSION_DURATION_MAX * 60)
        self.session_actions = 0
        session_minutes = self.session_duration / 60
        self.session_target_actions = max(2, int(session_minutes / 5))
        
        self.log_event("session_start", 
                      f"Session started ({self.session_duration/60:.0f}m, target {self.session_target_actions} actions)",
                      {"duration_min": self.session_duration/60, "target_actions": self.session_target_actions})
    
    def end_session(self):
        """End current session and start break"""
        self.session_active = False
        session_elapsed = (self.sim_time - self.session_start_time).total_seconds()
        
        self.break_active = True
        self.break_start_time = self.sim_time
        self.break_duration = random.randint(self.BREAK_DURATION_MIN * 60, self.BREAK_DURATION_MAX * 60)
        
        self.log_event("session_end",
                      f"Session ended ({session_elapsed/60:.0f}m, {self.session_actions} actions) → Break ({self.break_duration/60:.0f}m)",
                      {"session_minutes": session_elapsed/60, "actions": self.session_actions, "break_minutes": self.break_duration/60})
    
    def is_session_complete(self) -> bool:
        """Check if session has ended"""
        if not self.session_active:
            return False
        
        elapsed = (self.sim_time - self.session_start_time).total_seconds()
        return elapsed >= self.session_duration
    
    def is_break_complete(self) -> bool:
        """Check if break has ended"""
        if not self.break_active:
            return False
        
        elapsed = (self.sim_time - self.break_start_time).total_seconds()
        return elapsed >= self.break_duration
    
    def should_take_action(self) -> bool:
        """Check if enough time has passed since last action"""
        if self.last_action_time is None:
            return True
        
        elapsed = (self.sim_time - self.last_action_time).total_seconds()
        min_interval = self.MIN_ACTION_INTERVAL_SEC
        
        if elapsed < min_interval:
            return False
        
        # Probability-based action pacing
        if elapsed < min_interval * 2:
            chance = 0.3 + (elapsed - min_interval) / min_interval * 0.5
            return random.random() < chance
        else:
            return True
    
    def get_action_type(self) -> str:
        """Randomly select action type"""
        # Weight: 70% likes, 20% replies, 10% follows
        roll = random.random()
        if roll < 0.7:
            return "like"
        elif roll < 0.9:
            return "reply"
        else:
            return "follow"
    
    def check_rate_limit(self, action_type: str) -> bool:
        """Check if action hits rate limit"""
        hour_key = self.sim_time.strftime("%H")
        
        if hour_key not in self.actions_by_hour:
            self.actions_by_hour[hour_key] = {"like": 0, "reply": 0, "follow": 0}
        
        hour_count = self.actions_by_hour[hour_key][action_type]
        daily_count = self.actions_by_day[action_type]
        
        if action_type == "like":
            hourly_limit = self.HOURLY_LIMIT_LIKE
            daily_limit = self.DAILY_LIMIT_LIKE
        elif action_type == "reply":
            hourly_limit = self.HOURLY_LIMIT_REPLY
            daily_limit = self.DAILY_LIMIT_REPLY
        else:  # follow
            hourly_limit = self.HOURLY_LIMIT_FOLLOW
            daily_limit = self.DAILY_LIMIT_FOLLOW
        
        if hour_count >= hourly_limit:
            return False  # Blocked by hourly limit
        
        if daily_count >= daily_limit:
            return False  # Blocked by daily limit
        
        return True
    
    def check_cluster_detection(self) -> bool:
        """Check if cluster detection is triggered"""
        # Remove actions older than 10 minutes
        cutoff_time = self.sim_time - timedelta(minutes=self.CLUSTER_THRESHOLD_MINUTES)
        self.recent_actions = [(a, t) for a, t in self.recent_actions if t > cutoff_time]
        
        # Check if we have 8+ actions in last 10 minutes
        if len(self.recent_actions) >= self.CLUSTER_THRESHOLD_ACTIONS:
            return True
        
        return False
    
    def take_action(self, action_type: str):
        """Simulate taking an action"""
        self.last_action_time = self.sim_time
        self.session_actions += 1
        self.actions_by_day[action_type] += 1
        
        hour_key = self.sim_time.strftime("%H")
        if hour_key not in self.actions_by_hour:
            self.actions_by_hour[hour_key] = {"like": 0, "reply": 0, "follow": 0}
        self.actions_by_hour[hour_key][action_type] += 1
        
        self.recent_actions.append((action_type, self.sim_time))
        self.consecutive_errors = 0  # Reset error counter on success
        
        action_labels = {
            "like": "❤️  Liked",
            "reply": "💬 Replied",
            "follow": "👤 Followed"
        }
        
        progress = f"{self.session_actions}/{self.session_target_actions}" if self.session_active else "?"
        self.log_event("action", 
                      f"{action_labels[action_type]} ({progress})",
                      {"action_type": action_type, "session_progress": progress})
    
    def simulate_error(self) -> bool:
        """Randomly simulate an error (5% chance per action)"""
        if random.random() < 0.05:  # 5% error rate
            self.consecutive_errors += 1
            
            if self.consecutive_errors >= 3:
                # Trigger detection cooldown
                self.error_cooldown_active = True
                self.error_cooldown_until = self.sim_time + timedelta(minutes=random.randint(30, 120))
                self.log_event("error", 
                              "Too many errors → Detection cooldown activated",
                              {"cooldown_minutes": (self.error_cooldown_until - self.sim_time).total_seconds() / 60})
                return False
            else:
                wait_sec = 2 ** self.consecutive_errors - 1  # Exponential backoff
                self.log_event("error",
                              f"Error occurred (exponential backoff: {wait_sec}s)",
                              {"consecutive_errors": self.consecutive_errors, "wait_sec": wait_sec})
                return True
        
        return True
    
    def step(self, minutes: int = 1):
        """Advance simulation by N minutes"""
        self.sim_time += timedelta(minutes=minutes)
    
    def run(self, start_time: datetime, duration_hours: int = 24):
        """Run full 24-hour simulation"""
        self.sim_time = start_time
        self.start_time = start_time
        end_time = start_time + timedelta(hours=duration_hours)
        
        print(f"\n{'='*80}")
        print(f"24-HOUR BEHAVIORAL SIMULATION")
        print(f"{'='*80}")
        print(f"Start: {start_time.strftime('%Y-%m-%d %H:%M')}")
        print(f"End: {end_time.strftime('%Y-%m-%d %H:%M')}")
        print(f"Config: Active {self.ACTIVE_START_HOUR}:00-{self.ACTIVE_END_HOUR}:00")
        print(f"Daily limits: {self.DAILY_LIMIT_LIKE} likes, {self.DAILY_LIMIT_REPLY} replies, {self.DAILY_LIMIT_FOLLOW} follows")
        print(f"{'='*80}\n")
        
        # Step through simulation (variable intervals for efficiency)
        while self.sim_time < end_time:
            # Check if error cooldown is active
            if self.error_cooldown_active and self.sim_time > self.error_cooldown_until:
                self.error_cooldown_active = False
                self.log_event("recovery", "Detection cooldown expired, resuming", {})
            
            # Check active hours
            if not self.should_be_active():
                # Outside active hours - sleep until next window
                wait_sec = self.get_time_until_active()
                
                if wait_sec > 0:
                    self.log_event("sleep", f"Outside active hours ({self.sim_time.hour:02d}:00) → sleeping {wait_sec//3600}h",
                                 {"hours_until_active": wait_sec // 3600})
                    # Jump to next active window
                    self.sim_time = self.sim_time + timedelta(seconds=wait_sec)
                    continue
            
            # Check if in break period
            if self.break_active:
                if self.is_break_complete():
                    self.break_active = False
                    self.log_event("break_end", "Break ended, ready for next session", {})
                else:
                    # Continue break
                    elapsed = (self.sim_time - self.break_start_time).total_seconds()
                    remaining = self.break_duration - elapsed
                    self.step(5)  # Skip ahead 5 min
                    continue
            
            # Start session if not active
            if not self.session_active:
                self.start_session()
            
            # Check if session is complete
            if self.session_active and self.is_session_complete():
                self.end_session()
                self.step(1)
                continue
            
            # Check if should take action
            if self.session_active and not self.should_take_action():
                # Not ready for action yet - step ahead
                self.step(random.randint(1, 3))
                continue
            
            # Skip if error cooldown active
            if self.error_cooldown_active:
                self.step(5)
                continue
            
            # Decide on action
            action_type = self.get_action_type()
            
            # Check rate limits
            if not self.check_rate_limit(action_type):
                action_labels = {"like": "Like", "reply": "Reply", "follow": "Follow"}
                hour_key = self.sim_time.strftime("%H")
                hour_count = self.actions_by_hour[hour_key][action_type]
                daily_count = self.actions_by_day[action_type]
                
                if action_type == "like":
                    hourly_limit = self.HOURLY_LIMIT_LIKE
                    daily_limit = self.DAILY_LIMIT_LIKE
                elif action_type == "reply":
                    hourly_limit = self.HOURLY_LIMIT_REPLY
                    daily_limit = self.DAILY_LIMIT_REPLY
                else:
                    hourly_limit = self.HOURLY_LIMIT_FOLLOW
                    daily_limit = self.DAILY_LIMIT_FOLLOW
                
                rate_limit_type = "hourly" if hour_count >= hourly_limit else "daily"
                self.log_event("rate_limit",
                              f"{action_labels[action_type]} blocked ({rate_limit_type})",
                              {"action": action_type, "hour_count": hour_count, "daily_count": daily_count})
                self.step(5)
                continue
            
            # Check cluster detection
            if self.check_cluster_detection():
                self.log_event("cluster_detection",
                              f"Cluster detected! 8+ actions in 10 min → pausing engagement",
                              {"recent_actions": len(self.recent_actions)})
                # Long pause to break cluster
                self.step(15)
                continue
            
            # Take action and check for errors
            if self.simulate_error():
                self.take_action(action_type)
            
            # Step ahead to next action interval
            next_step = random.randint(2, 5)  # 2-5 min
            self.step(next_step)
    
    def print_timeline(self):
        """Print detailed timeline"""
        print("\n" + "="*80)
        print("DETAILED 24-HOUR TIMELINE")
        print("="*80 + "\n")
        
        for event in self.events:
            time_str = event.sim_time.strftime("%H:%M")
            event_symbols = {
                "session_start": "▶️ ",
                "session_end": "⏸️ ",
                "action": "  ",
                "rate_limit": "🚫",
                "cluster_detection": "🔴",
                "error": "⚠️ ",
                "recovery": "✅",
                "sleep": "😴",
                "break_end": "🔄",
            }
            symbol = event_symbols.get(event.event_type, "  ")
            print(f"{time_str} {symbol} {event.description}")
    
    def analyze_patterns(self):
        """Analyze patterns for detection risk"""
        print("\n" + "="*80)
        print("PATTERN ANALYSIS & DETECTION RISK")
        print("="*80 + "\n")
        
        # Action frequency analysis
        print("📊 ACTION FREQUENCY:")
        for hour_key in sorted(self.actions_by_hour.keys()):
            actions = self.actions_by_hour[hour_key]
            total_hour = sum(actions.values())
            if total_hour > 0:
                print(f"  {hour_key}:00 → {total_hour} actions (Likes: {actions['like']}, Replies: {actions['reply']}, Follows: {actions['follow']})")
        
        print(f"\n  Daily totals: {self.actions_by_day['like']} likes, {self.actions_by_day['reply']} replies, {self.actions_by_day['follow']} follows")
        
        # Session analysis
        print("\n📱 SESSION PATTERNS:")
        session_starts = [e for e in self.events if e.event_type == "session_start"]
        session_gaps = []
        
        for i in range(len(session_starts) - 1):
            gap = (session_starts[i+1].sim_time - session_starts[i].sim_time).total_seconds() / 60
            session_gaps.append(gap)
        
        if session_gaps:
            avg_gap = sum(session_gaps) / len(session_gaps)
            min_gap = min(session_gaps)
            max_gap = max(session_gaps)
            print(f"  Sessions per day: {len(session_starts)}")
            print(f"  Session gap distribution: {min_gap:.0f}m - {max_gap:.0f}m (avg: {avg_gap:.0f}m)")
            
            # Check if too regular
            variance = sum((g - avg_gap) ** 2 for g in session_gaps) / len(session_gaps)
            if variance < 1000:  # Low variance = suspicious
                print(f"  ⚠️  LOW VARIANCE: Sessions are suspiciously regular (variance: {variance:.0f})")
            else:
                print(f"  ✓ Good randomness (variance: {variance:.0f})")
        
        # Action interval analysis
        print("\n⏱️  ACTION TIMING:")
        action_events = [e for e in self.events if e.event_type == "action"]
        inter_action_times = []
        
        for i in range(len(action_events) - 1):
            interval = (action_events[i+1].sim_time - action_events[i].sim_time).total_seconds() / 60
            inter_action_times.append(interval)
        
        if inter_action_times:
            avg_interval = sum(inter_action_times) / len(inter_action_times)
            min_interval = min(inter_action_times)
            max_interval = max(inter_action_times)
            print(f"  Total actions: {len(action_events)}")
            print(f"  Interval distribution: {min_interval:.1f}m - {max_interval:.1f}m (avg: {avg_interval:.1f}m)")
            
            variance = sum((t - avg_interval) ** 2 for t in inter_action_times) / len(inter_action_times)
            if variance < 0.5:
                print(f"  ⚠️  SUSPICIOUS REGULARITY: Action intervals too consistent (variance: {variance:.2f})")
            else:
                print(f"  ✓ Good action randomness (variance: {variance:.2f})")
        
        # Error and recovery
        print("\n🛡️  SAFETY:")
        errors = [e for e in self.events if e.event_type == "error"]
        rate_limits = [e for e in self.events if e.event_type == "rate_limit"]
        clusters = [e for e in self.events if e.event_type == "cluster_detection"]
        
        print(f"  Errors encountered: {len(errors)}")
        print(f"  Rate limit blocks: {len(rate_limits)}")
        print(f"  Cluster detections: {len(clusters)}")
        
        if len(errors) == 0:
            print(f"  ✓ No errors in 24h (realistic)")
        elif len(errors) > 5:
            print(f"  ⚠️  Too many errors (>5) may trigger detection")
        
        # Behavioral metrics
        print("\n🎯 BEHAVIORAL SCORE:")
        
        scores = {
            "Realism": 100,
            "Randomness": 100,
            "Safety compliance": 100,
        }
        
        # Deduct for suspicious patterns
        if not session_gaps or variance < 1000:
            scores["Randomness"] -= 20
        
        if inter_action_times and sum((t - avg_interval) ** 2 for t in inter_action_times) / len(inter_action_times) < 0.5:
            scores["Randomness"] -= 15
        
        if len(rate_limits) > 2:
            scores["Safety compliance"] -= 20
        
        if len(clusters) > 0:
            scores["Safety compliance"] -= 30
        
        for metric, score in scores.items():
            bar = "█" * (score // 10) + "░" * ((100 - score) // 10)
            print(f"  {metric:<20} {bar} {score}%")
        
        overall = sum(scores.values()) // len(scores)
        print(f"\n  OVERALL DETECTION RISK: {100 - overall}% {'🟢 LOW' if overall >= 80 else '🟡 MEDIUM' if overall >= 60 else '🔴 HIGH'}")


if __name__ == "__main__":
    # Start simulation at 6 AM (before active hours)
    start_time = datetime(2026, 3, 12, 6, 0)
    
    simulator = BotSimulator()
    simulator.run(start_time, duration_hours=24)
    
    simulator.print_timeline()
    simulator.analyze_patterns()
    
    print("\n" + "="*80)
    print("SIMULATION COMPLETE")
    print("="*80 + "\n")
