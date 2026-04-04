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
from logger_setup import log
from config import Config


def _process_single_tweet(tweet, page, rate_limiter, error_handler,
                           content_engine, search_keyword, feedback):
    """
    Process a single tweet for engagement actions.
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

        # ===== INTENT-BASED ENGAGEMENT ROUTING =====
        should_try_reply = False
        use_curiosity = False

        if intent == 3:
            was_high_intent = True
            should_try_reply = True
            use_curiosity = True
            log.info(f"🎯 HIGH INTENT: {tweet_text[:60]}...")
        elif intent == 2:
            should_try_reply = random.random() < 0.30
        else:
            should_try_reply = random.random() < Config.REPLY_PROBABILITY

        if should_try_reply:
            actions, errors = _attempt_reply(
                tweet, page, rate_limiter, error_handler, content_engine,
                search_keyword, tweet_text, intent, intent_label,
                use_curiosity, feedback, reflection_summary,
            )
            actions_taken += actions
            errors_in_cycle += errors

        # FOLLOW (higher chance for high-intent users)
        follow_chance = Config.FOLLOW_PROBABILITY
        if intent == 3:
            follow_chance = 0.60
        elif intent == 2:
            follow_chance = 0.30

        if random.random() < follow_chance:
            actions, errors = _attempt_follow(
                tweet, rate_limiter, error_handler, intent_label, feedback
            )
            actions_taken += actions
            errors_in_cycle += errors

        # QUOTE TWEET (10% chance)
        if random.random() < 0.10:
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
