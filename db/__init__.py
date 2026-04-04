"""
db package — re-exports all public functions so existing
`from database import ...` callers continue to work unchanged
after database.py is replaced with `from db import ...`.

Import map:
  db.schema      → init_db
  db.posts       → is_duplicate, save_post, count_posts_today,
                   get_last_daily_post_date, has_posted_today
  db.interactions → log_engagement, get_reply_outcomes
  db.follows     → save_follow, get_stale_follows, mark_unfollowed, get_follow_stats
  db.conversions → init_conversion_tracking, log_conversion,
                   get_recent_conversions, get_conversion_stats
  db.search_log  → init_search_log, log_search, get_phrase_stats,
                   reflect_and_adapt, optimize_and_reflect
"""

from db.schema import init_db

from db.posts import (
    is_duplicate,
    save_post,
    count_posts_today,
    get_last_daily_post_date,
    has_posted_today,
)

from db.interactions import (
    log_engagement,
    get_reply_outcomes,
)

from db.follows import (
    save_follow,
    get_stale_follows,
    mark_unfollowed,
    get_follow_stats,
)

from db.conversions import (
    init_conversion_tracking,
    log_conversion,
    get_recent_conversions,
    get_conversion_stats,
)

from db.search_log import (
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
