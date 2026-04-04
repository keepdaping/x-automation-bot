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
                   use_curiosity, feedback, reflection_summary=""):
    """Attempt to reply to a tweet. Returns (actions_taken, errors_in_cycle)"""
    actions_taken = 0
    errors_in_cycle = 0

    if rate_limiter.can_perform_action("reply")[0]:
        try:
            should_reply, reason = should_reply_to_tweet_safe(tweet_text)

            if should_reply:
                # --- Reply generation strategy ---
                if use_curiosity and getattr(Config, "GROK_STYLE", True):
                    # Grok-style: direct, truth-seeking, bypasses curiosity fluff
                    user_msg = f'Reply to this tweet from someone who needs real help:\n\n"{tweet_text}"'
                    if reflection_summary:
                        user_msg += f"\n\nContext about their pain: {reflection_summary}"
                    generated_text = generate_contextual_reply(
                        tweet_text=tweet_text,
                        system_prompt=Config.GROK_SYSTEM_INSTRUCTION,
                        user_message=user_msg,
                    )
                    # Moderation guard — Grok path skips content_engine so validate inline
                    from content.content_moderator import ContentModerator
                    _grok_valid = (
                        generated_text
                        and len(generated_text.strip()) >= 8
                        and ContentModerator.validate(generated_text)[0]
                        and not ContentModerator.is_generic(generated_text)
                    )
                    if _grok_valid:
                        result = GenerationResult(
                            text=generated_text,
                            source="grok",
                            quality_score=0.85,
                        )
                        reply_type = "grok"
                    else:
                        log.warning("Grok reply failed moderation — falling back to curiosity")
                        result = content_engine.generate_curiosity_reply(tweet_text)
                        reply_type = "curiosity"
                elif use_curiosity:
                    result = content_engine.generate_curiosity_reply(tweet_text)
                    reply_type = "curiosity"
                else:
                    result = content_engine.generate_reply(tweet_text)
                    reply_type = "standard"

                reply = result.text

                if reply and len(reply) > 0:
                    success, reply_id = reply_tweet(page, tweet, reply)
                    if success:
                        rate_limiter.record_action("reply", success=True, target_id=reply_id)
                        actions_taken += 1
                        error_handler.reset_error_counter()
                        log.info(
                            f"✓ Replied [{reply_type}] "
                            f"(intent={intent_label}, quality={result.quality_score:.2f}) "
                            f"| Reply ID: {reply_id}"
                        )

                        # Feedback logged here (single source of truth)
                        try:
                            tweet_id = tweet.get_attribute("data-testid-tweet-id") or ""
                            feedback.log_reply(
                                tweet_id=tweet_id,
                                reply_id=reply_id or "",
                                user_handle="",
                                tweet_text=tweet_text,
                                reply_text=reply,
                                intent=intent_label,
                                reply_style=reply_type,
                                reflection_summary=reflection_summary,
                            )
                        except Exception as e:
                            log.warning(f"Feedback log failed: {e}")

                    else:
                        rate_limiter.record_action("reply", success=False)
        except Exception as e:
            should_retry, wait_seconds = error_handler.handle_error(e, "reply_tweet")
            rate_limiter.record_action("reply", success=False)
            errors_in_cycle += 1
            if should_retry and wait_seconds > 0:
                time.sleep(wait_seconds)

    return actions_taken, errors_in_cycle
