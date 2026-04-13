"""
Reply attempt logic — generation, moderation, posting, and feedback logging.
"""

import time

from actions.reply import reply_tweet
from content.engine import GenerationResult
from core.generator import generate_contextual_reply
from utils.language_handler import should_reply_to_tweet_safe
from logger_setup import log
from config import Config


def _attempt_reply(tweet, page, rate_limiter, error_handler, content_engine,
                   search_keyword, tweet_text, intent, intent_label,
                   use_curiosity, feedback, reflection_summary="",
                   reply_style_weights: dict = None):
    """Attempt to reply to a tweet. Returns (actions_taken, errors_in_cycle)"""
    actions_taken = 0
    errors_in_cycle = 0

    # ── Rate limiter check (logged, not silent) ────────────────────────────
    can_reply, limit_reason = rate_limiter.can_perform_action("reply")
    if not can_reply:
        log.warning(f"[ReplyHandler] SKIP — rate limiter: {limit_reason}")
        return actions_taken, errors_in_cycle

    log.info("→ Attempting reply...")
    try:
        # ── Language filter ────────────────────────────────────────────────
        should_reply, reason = should_reply_to_tweet_safe(tweet_text)
        if not should_reply:
            log.warning(f"[ReplyHandler] SKIP — language filter: {reason}")
            return actions_taken, errors_in_cycle

        # ── Reply style selection via UCB1 Bandit ──────────────────────────
        # use_curiosity=False  → always "standard" (low intent)
        # use_curiosity=True   → bandit picks from all three styles
        from core.bandit import get_reply_bandit
        _bandit = get_reply_bandit()

        if not use_curiosity:
            selected_style = "standard"
        elif reply_style_weights:
            import random as _random
            arms = list(reply_style_weights.keys())
            wts  = [reply_style_weights[a] for a in arms]
            selected_style = _random.choices(arms, weights=wts, k=1)[0]
        else:
            selected_style = _bandit.select()

        log.debug(f"[ReplyHandler] Selected style: {selected_style} (use_curiosity={use_curiosity})")

        # ── Generate reply ─────────────────────────────────────────────────
        if selected_style == "grok" and getattr(Config, "GROK_STYLE", True):
            user_msg = f'Reply to this tweet from someone who needs real help:\n\n"{tweet_text}"'
            if reflection_summary:
                user_msg += f"\n\nContext about their pain: {reflection_summary}"
            generated_text = generate_contextual_reply(
                tweet_text=tweet_text,
                system_prompt=Config.GROK_SYSTEM_INSTRUCTION,
                user_message=user_msg,
            )
            from content.content_moderator import ContentModerator
            generated_text = ContentModerator.sanitize_output(generated_text)
            _grok_valid = (
                generated_text
                and len(generated_text.strip()) >= 8
                and ContentModerator.validate(generated_text)[0]
                and not ContentModerator.is_generic(generated_text)
            )
            if _grok_valid:
                result = GenerationResult(text=generated_text, source="grok", quality_score=0.85)
                reply_type = "grok"
            else:
                log.warning("Grok reply failed moderation — falling back to curiosity")
                result = content_engine.generate_curiosity_reply(tweet_text)
                reply_type = "curiosity"
        elif selected_style == "curiosity":
            result = content_engine.generate_curiosity_reply(tweet_text)
            reply_type = "curiosity"
        else:
            result = content_engine.generate_reply(tweet_text)
            reply_type = "standard"

        reply = result.text

        if not reply or len(reply) == 0:
            log.warning(f"[ReplyHandler] FAIL — empty reply text (source={result.source}, error={result.error})")
            return actions_taken, errors_in_cycle

        log.debug(f"→ Generated reply ({len(reply)} chars, style={reply_type}): {reply[:80]}")

        # ── Execute reply via Playwright ───────────────────────────────────
        success, reply_id = reply_tweet(page, tweet, reply)
        if success:
            rate_limiter.record_action("reply", success=True, target_id=reply_id)
            actions_taken += 1
            error_handler.reset_error_counter()
            log.info(
                f"✓ Replied [{reply_type}] "
                f"(intent={intent_label}, quality={result.quality_score:.2f}) "
                f"| Reply ID: {reply_id or 'unknown'}"
            )

            # Feedback logged here (single source of truth)
            try:
                # Extract tweet ID from the article element's link, same strategy
                # as reply_id extraction in reply_tweet()
                import re as _re
                tweet_id = ""
                try:
                    link = tweet.locator("a[href*='/status/']").first
                    if link.count() > 0:
                        href = link.get_attribute("href") or ""
                        m = _re.search(r"/status/(\d+)", href)
                        if m:
                            tweet_id = m.group(1)
                except Exception:
                    pass

                # Extract user handle from the tweet's author link
                user_handle = ""
                try:
                    author_link = tweet.locator("a[role='link'][href^='/']").first
                    if author_link.count() > 0:
                        href = author_link.get_attribute("href") or ""
                        # href is like /username — strip the leading slash
                        candidate = href.lstrip("/").split("/")[0]
                        if candidate and candidate not in ("i", "home", "explore"):
                            user_handle = candidate
                except Exception:
                    pass

                feedback.log_reply(
                    tweet_id=tweet_id,
                    reply_id=reply_id or "",
                    user_handle=user_handle,
                    tweet_text=tweet_text,
                    reply_text=reply,
                    intent=intent_label,
                    reply_style=reply_type,
                    reflection_summary=reflection_summary,
                )
            except Exception as e:
                log.warning(f"Feedback log failed: {e}")
        else:
            log.warning("[ReplyHandler] FAIL — reply_tweet() returned False")
            rate_limiter.record_action("reply", success=False)

    except Exception as e:
        log.error(f"→ Reply FAILED: {e}")
        should_retry, wait_seconds = error_handler.handle_error(e, "reply_tweet")
        rate_limiter.record_action("reply", success=False)
        errors_in_cycle += 1
        if should_retry and wait_seconds > 0:
            time.sleep(wait_seconds)

    return actions_taken, errors_in_cycle
