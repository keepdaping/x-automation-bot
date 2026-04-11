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

    if rate_limiter.can_perform_action("reply")[0]:
        log.info("Attempting reply...")
        try:
            should_reply, reason = should_reply_to_tweet_safe(tweet_text)

            if not should_reply:
                log.info(f"Reply blocked by language filter: {reason}")

            if should_reply:
                # --- Reply style selection via UCB1 Bandit ---
                # Bandit chooses among all arms, but we constrain:
                #   use_curiosity=False  → always "standard" (low intent, no curiosity reply)
                #   use_curiosity=True   → bandit picks from all three styles
                from core.bandit import get_reply_bandit
                _bandit = get_reply_bandit()

                if not use_curiosity:
                    # Low/medium intent with no curiosity flag → standard only
                    selected_style = "standard"
                elif reply_style_weights:
                    # PolicyEngine provided adjusted weights → weighted random
                    # then let bandit record the selection for future learning
                    import random as _random
                    arms = list(reply_style_weights.keys())
                    wts  = [reply_style_weights[a] for a in arms]
                    selected_style = _random.choices(arms, weights=wts, k=1)[0]
                else:
                    # Pure bandit selection
                    selected_style = _bandit.select()

                log.debug(f"[ReplyHandler] Selected style: {selected_style} (use_curiosity={use_curiosity})")

                # --- Execute selected style ---
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
                elif selected_style == "curiosity":
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
                        log.warning("Reply failed: reply_tweet() returned False")
                        rate_limiter.record_action("reply", success=False)
                else:
                    log.warning("Reply failed: generated reply text was empty")
        except Exception as e:
            log.warning(f"Reply failed: {e}")
            should_retry, wait_seconds = error_handler.handle_error(e, "reply_tweet")
            rate_limiter.record_action("reply", success=False)
            errors_in_cycle += 1
            if should_retry and wait_seconds > 0:
                time.sleep(wait_seconds)

    return actions_taken, errors_in_cycle
