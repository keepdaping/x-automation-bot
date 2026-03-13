"""
Content generation engine - orchestrates the entire reply pipeline.

This is the single entry point for generating replies.
Uses: caching → prompt creation → LLM generation → validation → storage
"""

import time
from typing import Optional
from dataclasses import dataclass

from logger_setup import logger
from config import Config

from content.prompts import (
    get_reply_system_prompt,
    get_daily_tweet_system_prompt,
    get_fallback_replies,
)
from content.content_cache import ReplyCache
from content.content_moderator import ContentModerator
from core.generator import generate_contextual_reply, get_last_generation_metrics


@dataclass
class GenerationResult:
    """Result of reply generation."""
    text: str
    source: str  # "cache", "generated", "fallback"
    quality_score: float
    error: Optional[str] = None


class ContentEngine:
    """
    Production-grade content generation engine.
    
    Pipeline:
    1. Check cache (exact + semantic matching)
    2. Validate input tweet
    3. Generate new reply via LLM
    4. Validate generated reply
    5. Score quality
    6. Cache result
    7. Return with metadata
    """

    def __init__(self):
        """Initialize content engine with cache and validator."""
        self.cache = ReplyCache(expiry_days=Config.CACHE_EXPIRY_DAYS)
        self.moderator = ContentModerator()
        self.fallback_replies = get_fallback_replies()

        # Metrics
        self.metrics = {
            "cache_hits": 0,
            "cache_misses": 0,
            "generated": 0,
            "fallbacks": 0,
            "errors": 0,
        }

        logger.info("ContentEngine initialized")

    def generate_reply(
        self,
        tweet_text: str,
        use_cache: bool = True,
        force_generation: bool = False,
    ) -> GenerationResult:
        """
        Generate reply for a tweet.

        Args:
            tweet_text: Tweet to reply to
            use_cache: Whether to check cache first
            force_generation: Skip cache and always generate

        Returns:
            GenerationResult with reply text and metadata
        """
        try:
            # Step 1: Try cache first (unless forced)
            cached = None
            if use_cache and not force_generation:
                cached = self.cache.get(tweet_text)
                if cached:
                    self.metrics["cache_hits"] += 1
                    logger.debug(
                        f"Cache hit ({cached.get('source')}) - quality={cached.get('quality_score', 0):.2f}"
                    )
                    return GenerationResult(
                        text=cached["reply"],
                        source=cached.get("source", "cache"),
                        quality_score=cached.get("quality_score", 0.5),
                    )

            if not cached:
                self.metrics["cache_misses"] += 1

            # Step 2: Validate input
            is_valid, error = self.moderator.validate(tweet_text)
            if not is_valid:
                logger.warning(f"Invalid tweet input: {error}")
                self.metrics["fallbacks"] += 1
                return GenerationResult(
                    text=self._get_fallback(),
                    source="fallback",
                    quality_score=0.3,
                    error=f"Input validation failed: {error}",
                )

            # Step 3: Generate new reply via LLM
            system_prompt = get_reply_system_prompt()
            gen_start = time.time()
            generated_text = generate_contextual_reply(
                tweet_text=tweet_text,
                system_prompt=system_prompt,
            )
            gen_duration = time.time() - gen_start
            gen_metrics = get_last_generation_metrics()
            model = gen_metrics.get("model")
            tokens = gen_metrics.get("tokens")
            logger.info(
                f"Generated reply in {gen_duration:.2f}s (model={model}, tokens={tokens})"
            )
            self.metrics["generated"] += 1

            # Step 4: Validate generated reply
            is_valid, error = self.moderator.validate(generated_text)
            if not is_valid:
                logger.warning(f"Generated reply failed validation: {error}")
                self.metrics["fallbacks"] += 1
                return GenerationResult(
                    text=self._get_fallback(),
                    source="fallback",
                    quality_score=0.3,
                    error=f"Generation validation failed: {error}",
                )

            # Step 4b: Avoid generic replies
            if self.moderator.is_generic(generated_text):
                logger.debug("Generated reply is too generic, using fallback")
                self.metrics["fallbacks"] += 1
                return GenerationResult(
                    text=self._get_fallback(),
                    source="fallback",
                    quality_score=0.3,
                    error="Generated reply judged too generic",
                )

            # Step 5: Score quality
            quality_score = self.moderator.score_quality(generated_text)

            # Step 6: Check for duplicates (posted or cached)
            if self.moderator.is_duplicate(generated_text) or self.cache.is_duplicate_reply(
                generated_text
            ):
                logger.debug(
                    "Generated reply is duplicate of prior reply/cached reply, using fallback"
                )
                self.metrics["fallbacks"] += 1
                return GenerationResult(
                    text=self._get_fallback(),
                    source="fallback",
                    quality_score=0.3,
                    error="Reply is duplicate of previous replies",
                )

            # Step 7: Cache the result
            self.cache.set(tweet_text, generated_text, quality_score)

            return GenerationResult(
                text=generated_text,
                source="generated",
                quality_score=quality_score,
            )

        except Exception as e:
            logger.error(f"Content generation failed: {e}", exc_info=True)
            return GenerationResult(
                text=self._get_fallback(),
                source="fallback",
                quality_score=0.2,
                error=str(e),
            )

    def generate_daily_tweet(self, topic: str = None) -> str:
        """Generate a single daily tweet.

        Uses the same content generation pipeline but with a prompt optimized for original tweets.
        """
        # Seed the generator with a topic to influence the tweet (optional)
        seed = topic or "a short, engaging idea"
        system_prompt = get_daily_tweet_system_prompt()

        tweet = generate_contextual_reply(tweet_text=seed, system_prompt=system_prompt)
        return tweet.strip() if tweet else ""

    def _get_fallback(self) -> str:
        """Get a random fallback reply."""
        import random
        return random.choice(self.fallback_replies)

    def get_cache_stats(self) -> dict:
        """Get cache statistics."""
        return self.cache.get_stats()

    def clear_cache(self, days: int = 30) -> int:
        """
        Clear old cache entries.

        Args:
            days: Clear entries older than this many days

        Returns:
            Number of entries cleared
        """
        removed = self.cache.cleanup_old_entries(days)
        logger.info(f"Cleared {removed} cache entries older than {days} days")
        return removed


# Module-level singleton (optional, for convenience)
_engine_instance: Optional[ContentEngine] = None


def get_content_engine() -> ContentEngine:
    """Get or create singleton ContentEngine instance."""
    global _engine_instance
    if _engine_instance is None:
        _engine_instance = ContentEngine()
    return _engine_instance
