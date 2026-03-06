# moderator.py
"""
Content moderation pipeline.

Checks (in order):
  1. Length   — must not exceed Config.MAX_POST_LENGTH
  2. Keywords — must not contain blocked phrases
  3. Duplicate — must not match any previously *posted* hash

IMPORTANT: hashes are only recorded in the database AFTER a tweet is
successfully posted (in poster.py → record_post(status='posted')).
This module only *reads* the duplicate store — it never writes to it.
That separation eliminates the original bug where rejected posts were
being permanently blacklisted before they were ever published.
"""
from __future__ import annotations

import hashlib

from config import Config
from database import is_hash_seen
from logger_setup import log


def hash_content(text: str) -> str:
    """Stable SHA-256 hash of normalised text. Used as the duplicate key."""
    return hashlib.sha256(text.lower().strip().encode()).hexdigest()


def _within_length(text: str) -> tuple[bool, str | None]:
    if len(text) > Config.MAX_POST_LENGTH:
        return False, f"too_long ({len(text)} chars)"
    return True, None


def _passes_keyword_filter(text: str) -> tuple[bool, str | None]:
    lower = text.lower()
    for keyword in Config.BLOCKED_KEYWORDS:
        if keyword in lower:
            return False, f"blocked_keyword:'{keyword}'"
    return True, None


def _is_not_duplicate(content_hash: str) -> tuple[bool, str | None]:
    if is_hash_seen(content_hash):
        return False, "duplicate"
    return True, None


def check(text: str) -> tuple[bool, str | None]:
    """
    Run the full moderation pipeline.

    Returns:
        (True,  None)             — post is safe to publish
        (False, rejection_reason) — post must be discarded
    """
    content_hash = hash_content(text)

    for check_fn, arg in [
        (_within_length,        text),
        (_passes_keyword_filter, text),
        (_is_not_duplicate,     content_hash),
    ]:
        ok, reason = check_fn(arg)   # type: ignore[operator]
        if not ok:
            log.warning(f"Moderation rejected post — reason: {reason}")
            return False, reason

    return True, None


# ── Convenience alias kept for backwards compatibility ────────────────────────

def is_safe(text: str) -> bool:
    ok, _ = check(text)
    return ok
