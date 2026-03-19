"""
Content generation engine - single entry point for all content.

Tweet generation now uses:
- Structural patterns + seed scenarios (from prompts.py)
- Real-signal validation (has_real_signal)
- Vague content detection (is_vague_content)
- Retry with escalation (up to 3 attempts before fallback)
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


# =====================================================
# REAL-SIGNAL VALIDATION
# A tweet must contain concrete information, not just opinions
# =====================================================

# Tool names the account's niche cares about
KNOWN_TOOLS = [
    "n8n", "zapier", "make", "gpt", "gpt-4", "gpt-4o", "claude", "chatgpt",
    "openai", "anthropic", "supabase", "vercel", "nextjs", "next.js",
    "python", "playwright", "stripe", "notion", "airtable", "perplexity",
    "midjourney", "cursor", "github", "copilot", "langchain", "replicate",
    "huggingface", "firebase", "railway", "render", "fly.io", "docker",
    "postgres", "redis", "sqlite", "api", "webhook", "cron",
]

# Outcome words that indicate something concrete happened
OUTCOME_WORDS = [
    "broke", "fixed", "shipped", "built", "launched", "replaced", "saved",
    "lost", "earned", "charged", "paid", "cost", "dropped", "grew",
    "doubled", "tripled", "killed", "automated", "hired", "fired",
    "quit", "switched", "migrated", "deployed", "crashed", "failed",
    "sold", "closed", "landed", "signed",
]

# Patterns that match numbers with context
NUMBER_PATTERNS = [
    r"\$\d+",           # $50, $0.60
    r"\d+%",            # 40%, 3%
    r"\d+\s*(?:hours?|hrs?|mins?|minutes?|days?|weeks?|months?|years?)",  # 4 hours, 6 months
    r"\d+\s*(?:clients?|users?|people|devs?|runs?|calls?)",  # 3 clients, 10 users
    r"\d+x",            # 3x, 10x
    r"\d+k",            # 5k, 10k
]


def has_real_signal(text: str) -> bool:
    """Check if a tweet contains at least one concrete signal.
    
    A real signal is: a tool name, a number with context, or an outcome verb.
    Without at least one, the tweet is vague filler.
    """
    text_lower = text.lower()
    
    # Check for tool names
    for tool in KNOWN_TOOLS:
        if tool in text_lower:
            return True
    
    # Check for numbers with context
    for pattern in NUMBER_PATTERNS:
        if re.search(pattern, text_lower):
            return True
    
    # Check for outcome words
    for word in OUTCOME_WORDS:
        # Match whole word
        if re.search(rf"\b{word}\b", text_lower):
            return True
    
    return False


# Vague patterns that sound like opinions but contain zero information
VAGUE_PATTERNS = [
    r"^most people",
    r"^everyone",
    r"stop overthinking",
    r"start building",
    r"consistency is",
    r"the (real |only )?secret is",
    r"automation is the future",
    r"the tools are (already )?there",
    r"you (just )?need to",
    r"it'?s (really )?not that (hard|complicated|difficult)",
    r"the (real )?problem is (that )?people",
    r"nobody (wants|is willing) to",
    r"success (comes|is) (from|about)",
    r"(hard|real) work (is|beats)",
]


def is_vague_content(text: str) -> bool:
    """Detect tweets that pass moderation but contain no real information.
    
    These are the most dangerous failures — they look fine but perform terribly.
    """
    text_lower = text.lower().strip()
    
    for pattern in VAGUE_PATTERNS:
        if re.search(pattern, text_lower):
            return True
    
    return False


# Escalation prompts for retries
RETRY_ESCALATIONS = [
    "\n\nIMPORTANT: Your previous attempt was too vague. This time you MUST include a specific tool name (like n8n, Zapier, GPT-4) OR a number with context ($X, X hours, X%).",
    "\n\nCRITICAL: Two attempts were too generic. Write about a SPECIFIC situation: name the tool, state the number, describe what actually happened. Example structure: '[tool] did [thing]. [number] changed. [implication].'",
    "\n\nFINAL ATTEMPT: Use this exact structure — Line 1: '[my/client's] [task] used to take [X hours/cost $X]' Line 2: '[tool name] does it in [X minutes/for $X] now'. Be specific or this tweet won't be posted.",
]


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
        """Generate a daily tweet with real-signal validation and retry logic.
        
        Attempts up to 3 retries with escalating specificity prompts.
        Only falls back if all retries fail signal validation.
        """
        now = datetime.now(timezone.utc)
        day_of_year = now.timetuple().tm_yday

        pillar = Config.get_content_pillar(day_of_year)
        hook = Config.get_viral_hook()

        logger.info(f"Daily tweet: pillar={pillar['name']}, hook={hook}")

        max_retries = 3
        best_tweet = None
        best_signal = 0.0

        for attempt in range(max_retries + 1):
            # Build prompt — fresh pattern + seed each attempt
            system_prompt = get_daily_tweet_system_prompt(pillar=pillar, hook_format=hook)
            
            # Add escalation instruction on retries
            if attempt > 0 and attempt <= len(RETRY_ESCALATIONS):
                escalation = RETRY_ESCALATIONS[attempt - 1]
                system_prompt += escalation
                self.metrics["retries"] += 1
                logger.info(f"Retry {attempt}/{max_retries} — escalating specificity")

            seed = topic or pillar["description"]
            user_message = f"Write one original tweet about: {seed}"
            
            tweet = generate_contextual_reply(
                tweet_text=seed,
                system_prompt=system_prompt,
                user_message=user_message,
            )

            if not tweet or not tweet.strip():
                continue

            tweet = tweet.strip()

            # Validate basics
            is_valid, error = self.moderator.validate(tweet)
            if not is_valid:
                logger.debug(f"Attempt {attempt}: failed validation — {error}")
                continue

            # Check for vague content
            if is_vague_content(tweet):
                logger.info(f"Attempt {attempt}: vague content detected — retrying")
                if best_tweet is None:
                    best_tweet = tweet  # Keep as fallback
                continue

            # Check for real signal
            if has_real_signal(tweet):
                signal = self.moderator.signal_density(tweet)
                logger.info(f"✅ Tweet has real signal (density={signal:.2f}): {tweet[:60]}...")
                return tweet

            # No real signal but not vague — acceptable if we run out of retries
            signal = self.moderator.signal_density(tweet)
            if signal > best_signal:
                best_signal = signal
                best_tweet = tweet

            logger.info(f"Attempt {attempt}: no real signal (density={signal:.2f}) — retrying")

        # All retries exhausted — return best attempt
        if best_tweet:
            logger.warning(f"Posting best-effort tweet (no strong signal): {best_tweet[:60]}...")
            return best_tweet

        logger.error("All tweet generation attempts failed")
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
