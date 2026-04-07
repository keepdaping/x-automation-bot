"""
Backward-compatibility shim.
All logic has moved to the db/ package.
Existing callers (`from database import X`) continue to work unchanged.
"""

from db import (
    init_db,
    is_duplicate,
    save_post,
    count_posts_today,
    count_daily_posts_today,
    get_last_daily_post_date,
    has_posted_today,
    log_engagement,
    get_reply_outcomes,
    save_follow,
    get_stale_follows,
    mark_unfollowed,
    get_follow_stats,
    init_conversion_tracking,
    log_conversion,
    get_recent_conversions,
    get_conversion_stats,
    init_search_log,
    log_search,
    get_phrase_stats,
    reflect_and_adapt,
    optimize_and_reflect,
)

__all__ = [
    "init_db",
    "is_duplicate",
    "save_post",
    "count_posts_today",
    "count_daily_posts_today",
    "get_last_daily_post_date",
    "has_posted_today",
    "log_engagement",
    "get_reply_outcomes",
    "save_follow",
    "get_stale_follows",
    "mark_unfollowed",
    "get_follow_stats",
    "init_conversion_tracking",
    "log_conversion",
    "get_recent_conversions",
    "get_conversion_stats",
    "init_search_log",
    "log_search",
    "get_phrase_stats",
    "reflect_and_adapt",
    "optimize_and_reflect",
]
