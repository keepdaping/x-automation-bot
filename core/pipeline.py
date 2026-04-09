"""
Single-tweet processing pipeline — intent scoring, LLM reflection, and action routing.
"""

import random
import time

from utils.tweet_metrics import get_tweet_metrics
from utils.engagement_score import score_tweet
from utils.tweet_text import get_tweet_text
from utils.intent_scorer import score_intent, get_intent_label
from utils.llm_intent_scorer import get_llm_intent_scorer
from core.reply_handler import _attempt_reply
from core.follow_handler import _attempt_follow
from core.quote_handler import _attempt_quote
from core.policy import get_policy_engine
from logger_setup import log
from config import Config


def _process_single_tweet(tweet, page, rate_limiter, error_handler,
                           content_engine, search_keyword, feedback,
                           force_reply: bool = False):
    """
    Process a single tweet for engagement actions.

    Parameters
    ----------
    force_reply : bool
        When True, bypass the probability roll for replying on LOW-intent tweets.
        Used exclusively by the forced-fallback path in run_engagement() when the
        entire cycle would otherwise produce zero actions.

    Returns (actions_taken, errors_in_cycle, was_high_intent)
    """
    actions_taken = 0
    errors_in_cycle = 0

    was_high_intent = False

    try:
        metrics = get_tweet_metrics(tweet)
        engagement_score = score_tweet(metrics)
        tweet_text = get_tweet_text(tweet)
        intent = score_intent(tweet_text)
        intent_label = get_intent_label(intent)
        log.debug(f"Score: {engagement_score}, Intent: {intent_label}")

        # ===== CHANGE 8: LLM reflection on high-intent tweets =====
        reflection_summary = ""
        if intent == 3 and getattr(Config, "REFLECTION_ENABLED", True):
            try:
                llm_scorer = get_llm_intent_scorer()
                llm_result = llm_scorer.score(tweet_text)
                # Downgrade if the tweet is negated ("I WAS struggling but now I'm fine")
                if llm_result.get("negation_check"):
                    intent = min(intent, 2)
                    intent_label = get_intent_label(intent)
                    log.info(f"🔄 LLM downgraded intent (negation): {llm_result['reason']}")
                elif llm_result.get("intent_score", 3) < intent:
                    intent = llm_result["intent_score"]
                    intent_label = get_intent_label(intent)
                    log.info(f"🔄 LLM adjusted intent to {llm_result['level']}: {llm_result['reason']}")
                pain_points = llm_result.get("pain_points", [])
                reason = llm_result.get("reason", "")
                reflection_summary = (
                    f"Pain: {', '.join(pain_points)}. {reason}" if pain_points else reason
                )
                if reflection_summary:
                    log.info(f"🔍 Reflection: {reflection_summary}")
            except Exception as e:
                log.warning(f"LLM reflection skipped: {e}")

        # ===== POLICY-DRIVEN ENGAGEMENT ROUTING =====
        # PolicyEngine reads RewardAggregator data and returns evidence-adjusted
        # probabilities. Falls back to Config defaults when data is insufficient.
        import time as _time
        policy = get_policy_engine()
        probs = policy.get_action_probabilities({
            "intent":           intent,
            "keyword":          search_keyword,
            "engagement_score": engagement_score,
            "time_hour":        _time.gmtime().tm_hour,
        })

        should_try_reply = False
        use_curiosity = False

        if intent == 3:
            was_high_intent = True
            should_try_reply = True          # always engage high-intent
            use_curiosity = True
            log.info(f"🎯 HIGH INTENT: {tweet_text[:60]}...")
        elif force_reply:
            # Forced-fallback path: bypass probability roll.
            # Only called when the whole cycle would otherwise be silent.
            should_try_reply = True
            log.info(f"[Fallback] Forcing reply (intent={intent_label}): {tweet_text[:60]}...")
        else:
            roll = random.random()
            should_try_reply = roll < probs["reply_probability"]
            log.info(
                f"[Decision] intent={intent_label} | "
                f"reply_prob={probs['reply_probability']:.3f} | "
                f"roll={roll:.3f} | "
                f"reply={'YES' if should_try_reply else 'NO'} | "
                f"follow_prob={probs['follow_probability']:.3f}"
            )

        if should_try_reply:
            actions, errors = _attempt_reply(
                tweet, page, rate_limiter, error_handler, content_engine,
                search_keyword, tweet_text, intent, intent_label,
                use_curiosity, feedback, reflection_summary,
                reply_style_weights=probs["reply_style_weights"],
            )
            actions_taken += actions
            errors_in_cycle += errors

        # FOLLOW — probability sourced from policy (reward-adjusted)
        if random.random() < probs["follow_probability"]:
            actions, errors = _attempt_follow(
                tweet, rate_limiter, error_handler, intent_label, feedback
            )
            actions_taken += actions
            errors_in_cycle += errors

        # QUOTE TWEET — probability sourced from policy
        if random.random() < probs["quote_probability"]:
            actions, errors = _attempt_quote(
                tweet, page, rate_limiter, error_handler, content_engine
            )
            actions_taken += actions
            errors_in_cycle += errors

        time.sleep(random.uniform(1, 3))

    except Exception as e:
        log.error(f"Error processing tweet: {e}")
        errors_in_cycle += 1

    return actions_taken, errors_in_cycle, was_high_intent
