"""
Content generation engine - single entry point for all content.

Tweet generation now uses:
- Structural patterns + seed scenarios (from prompts.py)
- Real-signal validation (has_real_signal)
- Vague content detection (is_vague_content)
- Named role + strong ending enforcement
- Retry with mode-switching escalation (up to 3 attempts)
"""

import re
import time
from datetime import datetime, timezone
from typing import Optional
from dataclasses import dataclass

from logger_setup import logger
from config import Config
from content.prompts import (
    get_reply_system_prompt, get_daily_tweet_system_prompt,
    get_fallback_replies, get_quote_tweet_system_prompt,
    get_curiosity_reply_prompt, VOICE_RULES,
)
from content.content_cache import ReplyCache
from content.content_moderator import ContentModerator
from core.generator import generate_contextual_reply, get_last_generation_metrics


@dataclass
class GenerationResult:
    text: str
    source: str  # "cache", "generated", "fallback", "curiosity"
    quality_score: float
    signal_density: float = 0.0
    retries: int = 0
    error: Optional[str] = None


# Minimum signal density to post a fallback tweet. Below this, skip the slot entirely.
# Posting noise is worse than posting nothing.
MIN_FALLBACK_SIGNAL = 0.70  # Raised slightly to be stricter


class ContentEngine:
    def __init__(self):
        self.cache = ReplyCache(expiry_days=Config.CACHE_EXPIRY_DAYS)
        self.moderator = ContentModerator()
        self.fallback_replies = get_fallback_replies()
        self.metrics = {
            "cache_hits": 0, "cache_misses": 0, "generated": 0,
            "fallbacks": 0, "errors": 0, "retries": 0,
        }
        logger.info("ContentEngine initialized")

    def generate_reply(self, tweet_text: str, use_cache: bool = True, force_generation: bool = False) -> GenerationResult:
        try:
            # Step 1: Try cache
            cached = None
            if use_cache and not force_generation:
                cached = self.cache.get(tweet_text)
                if cached:
                    self.metrics["cache_hits"] += 1
                    return GenerationResult(text=cached["reply"], source=cached.get("source", "cache"), quality_score=cached.get("quality_score", 0.5))

            if not cached:
                self.metrics["cache_misses"] += 1

            # Step 2: Validate input tweet
            is_valid, error = self.moderator.validate(tweet_text)
            if not is_valid:
                self.metrics["fallbacks"] += 1
                return GenerationResult(text=self._get_fallback(), source="fallback", quality_score=0.3, error=f"Input validation: {error}")

            # Step 3: Generate via LLM
            system_prompt = get_reply_system_prompt()
            gen_start = time.time()
            generated_text = generate_contextual_reply(tweet_text=tweet_text, system_prompt=system_prompt)
            gen_duration = time.time() - gen_start
            gen_metrics = get_last_generation_metrics()
            logger.info(f"Generated reply in {gen_duration:.2f}s (model={gen_metrics.get('model')}, tokens={gen_metrics.get('tokens')})")
            self.metrics["generated"] += 1

            # Step 4: Validate output
            is_valid, error = self.moderator.validate(generated_text)
            if not is_valid:
                self.metrics["fallbacks"] += 1
                return GenerationResult(text=self._get_fallback(), source="fallback", quality_score=0.3, error=f"Output validation: {error}")

            if self.moderator.is_generic(generated_text):
                self.metrics["fallbacks"] += 1
                return GenerationResult(text=self._get_fallback(), source="fallback", quality_score=0.3, error="Too generic")

            # Step 5: Score + dedupe
            quality_score = self.moderator.score_quality(generated_text)

            if self.moderator.is_duplicate(generated_text) or self.cache.is_duplicate_reply(generated_text):
                self.metrics["fallbacks"] += 1
                return GenerationResult(text=self._get_fallback(), source="fallback", quality_score=0.3, error="Duplicate")

            # Step 6: Cache
            self.cache.set(tweet_text, generated_text, quality_score)

            return GenerationResult(text=generated_text, source="generated", quality_score=quality_score)

        except Exception as e:
            logger.error(f"Content generation failed: {e}", exc_info=True)
            return GenerationResult(text=self._get_fallback(), source="fallback", quality_score=0.2, error=str(e))

    def generate_daily_tweet(self, topic: str = None) -> str:
        """Generate a daily tweet with strict real-signal validation and retry logic.
        
        Retry strategy changes behavior per attempt:
            Attempt 0: Normal generation with structural pattern
            Retry 1: Forces displacement_report structure + named role
            Retry 2: Strips to minimum viable tweet (<120 chars) with strong ending
            Retry 3: Fill-in-the-blank template the model must complete
        
        Returns empty string if all attempts fail MIN_FALLBACK_SIGNAL threshold.
        Skipping a post slot is better than posting noise.
        """
        now = datetime.now(timezone.utc)
        day_of_year = now.timetuple().tm_yday

        pillar = Config.get_content_pillar(day_of_year)
        hook = Config.get_viral_hook()

        logger.info(f"Daily tweet: pillar={pillar['name']}, hook={hook}")

        max_retries = 3
        best_tweet = None
        best_signal = 0.0
        best_quality = 0.0

        # Retry strategies — each adds stricter constraints
        retry_strategies = [
            None,  # Attempt 0: normal generation
            # Retry 1: Force displacement_report + named role
            "\n\nYou MUST use this exact structure:\nLine 1: [old way — who did it (name role: VA/junior/CFO/etc.), how long, cost]\nLine 2: [new way — tool name + new cost]\nLine 3: [uncomfortable consequence for that person/role — be specific]\nInclude a real tool name, a real number, and a specific role. No hedging. End with tension.",
            # Retry 2: Minimum viable tweet with strong ending
            "\n\nWrite the SHORTEST possible tweet — under 120 characters. Format: [tool] replaced [task for specific role]. [one strong consequence line with stakes]. End with question or tension. No fluff. Must name a role.",
            # Retry 3: Fill-in-the-blank template (forces structure + role)
            "\n\nComplete this template EXACTLY (fill in the blanks, output only the result):\n'[specific role: VA/junior/CFO/etc.] used to spend [X hours/$X] on [task]. [tool name] does it for [X minutes/$X] now. [one uncomfortable sentence about what this means for them].'",
        ]

        for attempt in range(max_retries + 1):
            # Build fresh prompt — new pattern + seed each time
            system_prompt = get_daily_tweet_system_prompt(pillar=pillar, hook_format=hook)
            
            # Apply retry strategy
            if attempt > 0 and attempt < len(retry_strategies):
                strategy = retry_strategies[attempt]
                if strategy:
                    system_prompt += strategy
                self.metrics["retries"] += 1
                logger.info(f"Retry {attempt}/{max_retries} — switching generation mode")

            seed = topic or pillar["description"]
            user_message = f"Write one original tweet about: {seed}"
            
            tweet = generate_contextual_reply(
                tweet_text=seed,
                system_prompt=system_prompt,
                user_message=user_message,
            )

            if not tweet or not tweet.strip():
                logger.debug(f"Attempt {attempt}: empty generation")
                continue

            tweet = tweet.strip()

            # Gate 1: Basic validation
            is_valid, error = self.moderator.validate(tweet)
            if not is_valid:
                logger.debug(f"Attempt {attempt}: failed validation — {error}")
                continue

            # Gate 2: Vague content check
            if is_vague_content(tweet):
                logger.info(f"Attempt {attempt}: vague content detected — retrying")
                continue

            # Gate 3: Generic content check
            if self.moderator.is_generic(tweet):
                logger.info(f"Attempt {attempt}: generic content detected — retrying")
                continue

            # Gate 4: Named role check (forces specificity)
            if not self.moderator.has_named_role(tweet):
                logger.info(f"Attempt {attempt}: no named role — retrying")
                continue

            # Gate 5: Strong ending check (ensures punch)
            if not self.moderator.has_strong_ending(tweet):
                logger.info(f"Attempt {attempt}: weak ending — retrying")
                continue

            # Gate 6: Real signal check
            signal = self.moderator.signal_density(tweet)
            quality = self.moderator.score_quality(tweet)

            if has_real_signal(tweet):
                logger.info(f"✅ Tweet passed all gates (density={signal:.2f}, quality={quality:.2f}): {tweet[:60]}...")
                return tweet

            # Track best attempt
            if signal > best_signal or (signal == best_signal and quality > best_quality):
                best_signal = signal
                best_quality = quality
                best_tweet = tweet

            logger.info(f"Attempt {attempt}: signal too weak (density={signal:.2f}, quality={quality:.2f}) — retrying")

        # All retries exhausted — apply MIN_FALLBACK_SIGNAL floor
        if best_tweet and best_signal >= MIN_FALLBACK_SIGNAL:
            logger.warning(f"Posting best-effort tweet (signal={best_signal:.2f}, quality={best_quality:.2f}): {best_tweet[:60]}...")
            return best_tweet

        reason = f"best attempt signal ({best_signal:.2f}) below floor ({MIN_FALLBACK_SIGNAL})" if best_tweet else "all attempts failed"
        logger.warning(f"Skipping post — {reason}")

        return ""

    def generate_quote_text(self, tweet_text: str) -> str:
        """Generate commentary for a quote tweet."""
        system_prompt = get_quote_tweet_system_prompt()
        user_message = f"Write a short quote tweet commentary for this tweet:\n\n\"{tweet_text}\""
        text = generate_contextual_reply(tweet_text=tweet_text, system_prompt=system_prompt, user_message=user_message)
        return text.strip() if text else ""

    def generate_curiosity_reply(self, tweet_text: str) -> GenerationResult:
        """Generate a curiosity-driven reply for high-intent tweets."""
        try:
            system_prompt = get_curiosity_reply_prompt()
            gen_start = time.time()
            generated_text = generate_contextual_reply(
                tweet_text=tweet_text,
                system_prompt=system_prompt,
                user_message=f'Reply to this tweet from someone who needs help:\n\n"{tweet_text}"'
            )
            gen_duration = time.time() - gen_start
            gen_metrics = get_last_generation_metrics()
            logger.info(f"Curiosity reply in {gen_duration:.2f}s (model={gen_metrics.get('model')})")

            # Validate
            is_valid, error = self.moderator.validate(generated_text)
            if not is_valid:
                return self.generate_reply(tweet_text)

            quality_score = self.moderator.score_quality(generated_text)

            return GenerationResult(
                text=generated_text,
                source="curiosity",
                quality_score=quality_score,
            )
        except Exception as e:
            logger.error(f"Curiosity reply failed: {e}")
            return self.generate_reply(tweet_text)

    def _get_fallback(self) -> str:
        import random
        return random.choice(self.fallback_replies)

    def get_cache_stats(self) -> dict:
        return self.cache.get_stats()


_engine_instance: Optional[ContentEngine] = None


def get_content_engine() -> ContentEngine:
    global _engine_instance
    if _engine_instance is None:
        _engine_instance = ContentEngine()
    return _engine_instance