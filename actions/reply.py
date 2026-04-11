"""Reply to tweets with human-like typing."""

import time
from utils.human_behavior import random_delay, human_typing
from utils.selectors import REPLY_BUTTON, REPLY_TEXTAREA
from logger_setup import log


def reply_tweet(page, tweet, text, timeout=10000):
    """
    Reply to a tweet with human-like typing.
    Returns (success: bool, reply_id: str or None) so we can track it.
    """
    try:
        # ── Step 1: Find reply button ──────────────────────────────────────
        reply_btn = tweet.locator(REPLY_BUTTON).first
        if reply_btn.count() == 0:
            log.warning("→ Reply FAILED: reply button not found in tweet element")
            return False, None
        log.debug("→ Reply button found, clicking...")

        reply_btn.scroll_into_view_if_needed()
        time.sleep(0.5)

        try:
            reply_btn.click(timeout=timeout)
        except Exception as click_err:
            log.debug(f"Normal click failed ({click_err}), retrying with force=True")
            reply_btn.click(timeout=timeout, force=True)

        # ── Step 2: Wait for compose box ──────────────────────────────────
        log.debug("→ Waiting for reply textarea...")
        try:
            page.wait_for_selector(REPLY_TEXTAREA, timeout=timeout)
        except Exception as wait_err:
            log.warning(f"→ Reply FAILED: textarea did not appear — {wait_err}")
            return False, None

        time.sleep(1)

        # ── Step 3: Locate textarea (with fallback) ────────────────────────
        text_area = page.locator(REPLY_TEXTAREA).first
        if text_area.count() == 0:
            log.debug("Primary textarea selector missed, trying div[role='textbox']")
            text_area = page.locator("div[role='textbox']").first
        if text_area.count() == 0:
            log.warning("→ Reply FAILED: could not find reply textarea after compose box opened")
            return False, None
        log.debug("→ Textarea found, typing reply...")

        # ── Step 4: Type reply ─────────────────────────────────────────────
        human_typing(text_area, text, wpm=60)
        time.sleep(1)
        log.debug("→ Typing complete, submitting...")

        # ── Step 5: Submit ─────────────────────────────────────────────────
        # Prefer clicking the visible "Reply" submit button over keyboard shortcut,
        # which is fragile on X.com (shortcut is disabled inside compose modals).
        submitted = False
        submit_btn = page.locator("[data-testid='tweetButton']").last
        if submit_btn.count() > 0:
            try:
                submit_btn.click(timeout=5000)
                submitted = True
                log.debug("→ Submitted via tweetButton click")
            except Exception as sub_err:
                log.debug(f"tweetButton click failed ({sub_err}), falling back to Ctrl+Enter")

        if not submitted:
            page.keyboard.press("Control+Enter")
            log.debug("→ Submitted via Ctrl+Enter")

        time.sleep(1.5)

        # ── Step 6: Extract reply ID ───────────────────────────────────────
        reply_id = None
        try:
            time.sleep(2)
            your_reply = page.locator("article[data-testid='tweet']").last
            reply_id = your_reply.get_attribute("data-testid-tweet-id") or ""
            if not reply_id:
                log.debug("Could not extract reply_id — will track without it")
        except Exception as e:
            log.debug(f"Failed to get reply_id: {e}")

        random_delay()
        log.info("→ Reply SUCCESS")
        return True, reply_id

    except Exception as e:
        log.error(f"→ Reply FAILED: {e}")
        return False, None