"""Reply to tweets with human-like typing."""

import time
from utils.human_behavior import random_delay, human_typing
from utils.selectors import REPLY_BUTTON, REPLY_TEXTAREA
from logger_setup import log


# Ordered list of selectors tried for the reply-dialog submit button.
# X renders the same data-testid in both the nav compose box and the reply
# dialog, so we prefer the dialog-scoped version first.
_SUBMIT_SELECTORS = [
    "div[role='dialog'] [data-testid='tweetButton']",
    "div[role='dialog'] button[data-testid='tweetButton']",
    "[data-testid='tweetButton']",
]


def _find_enabled_submit(page, timeout_ms: int = 5000):
    """
    Return the first visible, enabled submit button or None.

    Tries each selector in _SUBMIT_SELECTORS and returns the first locator
    that (a) exists in the DOM, (b) is visible, and (c) is not disabled.
    Falls back to None so the caller can use Ctrl+Enter instead.
    """
    deadline = time.time() + timeout_ms / 1000
    while time.time() < deadline:
        for sel in _SUBMIT_SELECTORS:
            btn = page.locator(sel).last
            try:
                if btn.count() > 0 and btn.is_visible() and btn.is_enabled():
                    return btn
            except Exception:
                pass
        time.sleep(0.3)
    return None


def reply_tweet(page, tweet, text, timeout=10000):
    """
    Reply to a tweet with human-like typing.
    Returns (success: bool, reply_id: str | None).
    """
    try:
        # ── Step 1: Find and click the reply button on the tweet ───────────
        reply_btn = tweet.locator(REPLY_BUTTON).first
        if reply_btn.count() == 0:
            log.error("→ Reply selector not found: [data-testid='reply'] not in tweet element")
            return False, None

        reply_btn.scroll_into_view_if_needed()
        time.sleep(0.5)

        try:
            reply_btn.click(timeout=timeout)
        except Exception as click_err:
            log.debug(f"Normal click failed ({click_err}), retrying with force=True")
            try:
                reply_btn.click(timeout=timeout, force=True)
            except Exception as force_err:
                log.error(f"→ Reply selector click failed: {force_err}")
                return False, None

        # ── Step 2: Wait for compose textarea to appear ────────────────────
        log.debug("→ Waiting for reply textarea to become visible...")
        try:
            page.wait_for_selector(REPLY_TEXTAREA, state="visible", timeout=timeout)
        except Exception as wait_err:
            log.error(f"→ Reply selector not found: textarea never appeared — {wait_err}")
            return False, None

        time.sleep(0.8)

        # ── Step 3: Locate textarea with fallback ──────────────────────────
        text_area = page.locator(REPLY_TEXTAREA).first
        if text_area.count() == 0:
            log.debug("Primary textarea selector missed, trying div[role='textbox']")
            text_area = page.locator("div[role='dialog'] div[role='textbox']").first
        if text_area.count() == 0:
            text_area = page.locator("div[role='textbox']").first
        if text_area.count() == 0:
            log.error("→ Reply selector not found: could not locate textarea after modal opened")
            return False, None

        # ── Step 4: Type the reply ─────────────────────────────────────────
        log.info("→ Typing reply...")
        typed_ok = human_typing(text_area, text, wpm=60)
        if not typed_ok:
            log.error("→ Reply FAILED: human_typing() returned False")
            return False, None
        log.info("→ Typing complete")

        # Small pause so X registers the text and enables the submit button
        time.sleep(1.0)

        # ── Step 5: Find and click the submit button ───────────────────────
        log.info("→ Submitting reply...")
        submit_btn = _find_enabled_submit(page, timeout_ms=6000)

        if submit_btn is not None:
            try:
                submit_btn.click(timeout=5000)
                log.info("→ Reply submitted (tweetButton click)")
            except Exception as sub_err:
                log.error(f"→ Submit failed: tweetButton click raised — {sub_err}")
                # Last-resort keyboard fallback
                try:
                    page.keyboard.press("Control+Enter")
                    log.info("→ Reply submitted (Ctrl+Enter fallback)")
                except Exception as kb_err:
                    log.error(f"→ Submit failed: Ctrl+Enter also failed — {kb_err}")
                    return False, None
        else:
            # No enabled button found — try keyboard shortcut
            log.debug("→ No enabled submit button found, using Ctrl+Enter")
            try:
                page.keyboard.press("Control+Enter")
                log.info("→ Reply submitted (Ctrl+Enter)")
            except Exception as kb_err:
                log.error(f"→ Submit failed: {kb_err}")
                return False, None

        # Allow X to process the submission before we check for the reply ID
        time.sleep(2.0)

        # ── Step 6: Extract reply ID (best-effort) ─────────────────────────
        reply_id = None
        try:
            your_reply = page.locator("article[data-testid='tweet']").last
            if your_reply.count() > 0:
                reply_id = your_reply.get_attribute("data-testid-tweet-id") or ""
                if not reply_id:
                    log.debug("Reply ID not found in attribute — tracking without it")
        except Exception as e:
            log.debug(f"Failed to extract reply_id: {e}")

        random_delay()
        return True, reply_id

    except Exception as e:
        log.error(f"→ Reply FAILED (unhandled): {e}")
        return False, None
