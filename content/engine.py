"""
Content generation engine - orchestrates the entire reply pipeline.

This is the single entry point for generating replies.
Uses: caching → prompt creation → LLM generation → validation → storage
"""

from typing import Optional
from dataclasses import dataclass
import time

from logger_setup import logger
from config import Config

from content.prompts import get_reply_system_prompt, get_fallback_replies
from content.content_cache import ReplyCache
from content.content_moderator import ContentModerator
from core.generator import generate_contextual_reply, GeneratorResponse


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
    1. Expire old cache entries automatically
    2. Check cache (exact + semantic matching) and return stored score
    3. Validate input tweet
    4. Generate new reply via LLM (metrics tracked)
    5. Validate generated reply
    6. Score quality
    7. Avoid duplicates/generic replies
    8. Cache result with score
    9. Return with metadata
    """

    def __init__(self):
        """Initialize content engine with cache and validator."""
        # single persistent cache connection will be managed by ReplyCache
        self.cache = ReplyCache()
        self.moderator = ContentModerator()
        self.fallback_replies = get_fallback_replies()
        # footprint metric counters
        self.metrics = {
            "cache_hits": 0,
            "cache_misses": 0,
            "generated": 0,
            "fallbacks": 0,
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
            # automatic cache expiry if configured
            expiry = getattr(Config, "CACHE_EXPIRY_DAYS", 30)
            if expiry:
                self.cache.cleanup_old_entries(expiry)

            # Step 1: Try cache first (unless forced)
            if use_cache and not force_generation:
                cached = self.cache.get(tweet_text)
                if cached:
                    # returned tuple (reply, quality_score)
                    reply_text, quality_score = cached
                    self.metrics["cache_hits"] += 1
                    logger.debug(f"Cache hit (quality={quality_score:.2f})")
                    return GenerationResult(
                        text=reply_text,
                        source="cache",
                        quality_score=quality_score,
                    )
                else:
                    self.metrics["cache_misses"] += 1
                    logger.debug("Cache miss")

            # Step 2: Validate input
            is_valid, error = self.moderator.validate(tweet_text)
            if not is_valid:
                logger.warning(f"Invalid tweet input: {error}")
                return GenerationResult(
                    text=self._get_fallback(),
                    source="fallback",
                    quality_score=0.3,
                    error=f"Input validation failed: {error}",
                )

            # Step 3: Generate new reply via LLM
            system_prompt = get_reply_system_prompt()
            gen_start = time.perf_counter()
            resp: GeneratorResponse = generate_contextual_reply(
                tweet_text=tweet_text,
                system_prompt=system_prompt,
            )
            gen_time = time.perf_counter() - gen_start
            generated_text = resp.text
            logger.info(f"LLM generate: model={resp.model} time={gen_time:.2f}s tokens={resp.tokens}")

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

            # Step 5: Score quality
            quality_score = self.moderator.score_quality(generated_text)

            # Step 6: Check for duplicates or generic replies
            generic = {r.lower() for r in self.fallback_replies}
            if self.moderator.is_duplicate(generated_text) or \
               self.cache.is_reply_similar(generated_text) or \
               generated_text.lower() in generic:
                logger.debug("Generated reply considered duplicate/generic, using fallback")
                self.metrics["fallbacks"] += 1
                return GenerationResult(
                    text=self._get_fallback(),
                    source="fallback",
                    quality_score=0.3,
                    error="Reply is duplicate or too generic",
                )

            # Step 7: Cache the result
            self.cache.set(tweet_text, generated_text, quality_score)
            self.metrics["generated"] += 1

            return GenerationResult(
                text=generated_text,
                source="generated",
                quality_score=quality_score,
            )

        except Exception as e:
            logger.error(f"Content generation failed: {e}", exc_info=True)
            self.metrics["fallbacks"] += 1
            return GenerationResult(
                text=self._get_fallback(),
                source="fallback",
                quality_score=0.2,
                error=str(e),
            )

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
