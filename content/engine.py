"""
Content generation engine - single entry point for all content.
Now supports content pillars and viral hook formats for daily tweets.
"""

import time
from datetime import datetime, timezone
from typing import Optional
from dataclasses import dataclass

from logger_setup import logger
from config import Config
from content.prompts import get_reply_system_prompt, get_daily_tweet_system_prompt, get_fallback_replies, get_quote_tweet_system_prompt
from content.content_cache import ReplyCache
from content.content_moderator import ContentModerator
from core.generator import generate_contextual_reply, get_last_generation_metrics


@dataclass
class GenerationResult:
    text: str
    source: str  # "cache", "generated", "fallback"
    quality_score: float
    error: Optional[str] = None


class ContentEngine:
    def __init__(self):
        self.cache = ReplyCache(expiry_days=Config.CACHE_EXPIRY_DAYS)
        self.moderator = ContentModerator()
        self.fallback_replies = get_fallback_replies()
        self.metrics = {"cache_hits": 0, "cache_misses": 0, "generated": 0, "fallbacks": 0, "errors": 0}
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

            # Step 2: Validate input
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
        """Generate a daily tweet using content pillars and viral hooks."""
        now = datetime.now(timezone.utc)
        day_of_year = now.timetuple().tm_yday

        pillar = Config.get_content_pillar(day_of_year)
        hook = Config.get_viral_hook()

        logger.info(f"Daily tweet: pillar={pillar['name']}, hook={hook}")

        system_prompt = get_daily_tweet_system_prompt(pillar=pillar, hook_format=hook)
        seed = topic or pillar["description"]

        user_message = f"Write one original tweet about: {seed}"
        tweet = generate_contextual_reply(tweet_text=seed, system_prompt=system_prompt, user_message=user_message)
        return tweet.strip() if tweet else ""

    def generate_quote_text(self, tweet_text: str) -> str:
        """Generate commentary for a quote tweet."""
        system_prompt = get_quote_tweet_system_prompt()
        user_message = f"Write a short quote tweet commentary for this tweet:\n\n\"{tweet_text}\""
        text = generate_contextual_reply(tweet_text=tweet_text, system_prompt=system_prompt, user_message=user_message)
        return text.strip() if text else ""

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
