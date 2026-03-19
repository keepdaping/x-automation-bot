"""
Content generation engine.

CHANGES FROM PREVIOUS VERSION:
1. generate_daily_tweet returns GenerationResult (not str) — full observability
2. best_tweet fallback requires minimum signal threshold (0.50) before posting
3. is_generic() added to daily tweet validation chain
4. Retry strategy switches generation MODE per attempt (not just appends text)
5. require_opinion rotated every 3 posts via a simple counter
6. Cache key for daily tweets includes pattern name to prevent collision
7. has_real_signal uses stricter compound rule (anchor + consequence)
"""

import re
import time
import random
from datetime import datetime, timezone
from typing import Optional
from dataclasses import dataclass, field

from logger_setup import logger
from config import Config
from content.prompts import (
    get_reply_system_prompt, get_daily_tweet_system_prompt,
    get_fallback_replies, get_quote_tweet_system_prompt,
    get_curiosity_reply_prompt, _get_random_pattern, _get_random_seed,
    HOOK_FORMATS,
)
from content.content_cache import ReplyCache
from content.content_moderator import ContentModerator
from core.generator import generate_contextual_reply, get_last_generation_metrics


@dataclass
class GenerationResult:
    text: str
    source: str  # "cache", "generated", "retry_N", "fallback", "curiosity", "skip"
    quality_score: float
    signal_density: float = 0.0
    retries: int = 0
    error: Optional[str] = None


# =====================================================
# SIGNAL VALIDATION
# Compound rule: anchor (tool OR number) + consequence (outcome OR strong implication)
# Replaces the old 2-of-4 which was gameable via filler words ("now", "yet")
# =====================================================

KNOWN_TOOLS = [
    "n8n", "zapier", "make", "gpt", "gpt-4", "gpt-4o", "claude", "chatgpt",
    "openai", "anthropic", "supabase", "vercel", "nextjs", "next.js",
    "python", "playwright", "stripe", "notion", "airtable", "perplexity",
    "midjourney", "cursor", "github", "copilot", "langchain", "replicate",
    "huggingface", "firebase", "railway", "render", "fly.io", "docker",
    "postgres", "redis", "sqlite", "api", "webhook", "cron", "make.com",
]

OUTCOME_WORDS = [
    "broke", "fixed", "shipped", "built", "launched", "replaced", "saved",
    "lost", "earned", "charged", "paid", "cost", "dropped", "grew",
    "doubled", "tripled", "automated", "hired", "fired", "quit", "switched",
    "migrated", "deployed", "crashed", "failed", "sold", "closed", "landed",
    "deleted", "eliminated", "compressed", "reduced", "killed",
]

# Only specific phrases count as implication — not filler words like "now"/"yet"
STRONG_IMPLICATION_PHRASES = [
    "doesn't know yet", "still on retainer", "won't last", "for now",
    "this is how it starts", "gets cheaper", "changes what",
    "nobody got", "the job didn't", "they don't know",
    "asked why they're still", "what happens when",
    "that's somehow worse", "nobody talks about the part",
    "the math is", "they only see the",
    "nobody's scheduled", "that conversation",
    "budget review", "nobody's had",
    "still employed", "still exists",
    "last 20%", "80% of", "first 80",
    "doesn't know what", "no good answer",
    "awkward call", "nobody laughed",
]

NUMBER_PATTERNS = [
    r"\$\d+",
    r"\d+%",
    r"\d+\s*(?:hours?|hrs?|mins?|minutes?|days?|weeks?|months?|years?)",
    r"\d+\s*(?:clients?|users?|people|devs?|runs?|calls?)",
    r"\d+x",
    r"\d+k",
    r"\d+/(?:month|week|day|run|year|hr|hour)",
]


def _has_anchor(text: str) -> bool:
    """Tool name OR number with context."""
    t = text.lower()
    if any(tool in t for tool in KNOWN_TOOLS):
        return True
    if any(re.search(p, t) for p in NUMBER_PATTERNS):
        return True
    return False


def _has_consequence(text: str) -> bool:
    """Outcome verb OR strong implication phrase."""
    t = text.lower()
    if any(re.search(rf"\b{w}\b", t) for w in OUTCOME_WORDS):
        return True
    if any(phrase in t for phrase in STRONG_IMPLICATION_PHRASES):
        return True
    return False


def has_real_signal(text: str) -> bool:
    """
    Compound validation: must have ANCHOR + CONSEQUENCE.

    Anchor = tool name OR number with context
    Consequence = outcome verb OR strong implication phrase

    This replaces the old 2-of-4 check which allowed filler words
    ("now", "yet", "means") to satisfy the implication bucket.
    """
    return _has_anchor(text) and _has_consequence(text)


# Vague patterns — no change needed, these are accurate
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
    r"just start",
    r"take action",
    r"be consistent",
    r"trust the process",
    r"done is better than perfect",
    r"ship (it|fast|now)",
]


def is_vague_content(text: str) -> bool:
    t = text.lower().strip()
    return any(re.search(p, t) for p in VAGUE_PATTERNS)


# =====================================================
# RETRY STRATEGIES
# Each retry changes the generation MODE, not just adds text
# =====================================================

class RetryStrategy:
    @staticmethod
    def get_prompt(attempt: int, base_prompt: str, seed: str) -> str:
        if attempt == 1:
            # Switch to displacement_report — the most structurally constrained pattern
            return (
                base_prompt
                + "\n\nRETRY MODE — DISPLACEMENT REPORT ONLY:\n"
                + "Use EXACTLY this structure and nothing else:\n"
                + "Line 1: [who did it] + [how long] + [what it cost]\n"
                + "Line 2: [tool name] + [new cost per run or month]\n"
                + "Line 3: [the person's current status] + [what hasn't been said yet]\n"
                + "Must include: one tool name, one dollar amount, one named role.\n"
                + "If your output doesn't have all three, it won't be posted."
            )
        elif attempt == 2:
            # Minimum viable tweet — strip everything down
            return (
                "You are a tweet ghostwriter. Output ONLY the tweet.\n"
                "Write the shortest possible version of this scenario:\n"
                f"SCENARIO: {seed}\n\n"
                "Format: [tool] did [task]. costs [$X] now. [one person or role] [what changed for them].\n"
                "Under 120 characters. No filler. No motivation. Just the facts and the consequence.\n"
                "If you can't name a tool and a dollar amount, write nothing."
            )
        elif attempt == 3:
            # Fill-in-blank — force structure via template
            return (
                "You are a tweet ghostwriter. Output ONLY the tweet.\n"
                "Complete this template. Replace every [BRACKET] with real values.\n"
                "Do NOT keep the brackets in your output.\n\n"
                "[TOOL_NAME] replaced [SPECIFIC_TASK_WITH_DETAILS]\n"
                "old cost: [DOLLAR_OR_HOURS_PER_WEEK]. new cost: [DOLLAR_PER_RUN]\n"
                "[ROLE] [CURRENT_STATUS]. [ONE_LINE_IMPLICATION]\n\n"
                f"Base your values on: {seed}"
            )
        return base_prompt


# =====================================================
# MINIMUM FALLBACK SIGNAL
# Below this threshold, skip the post rather than post noise
# =====================================================
MIN_FALLBACK_SIGNAL = 0.50


class ContentEngine:
    def __init__(self):
        self.cache = ReplyCache(expiry_days=Config.CACHE_EXPIRY_DAYS)
        self.moderator = ContentModerator()
        self.fallback_replies = get_fallback_replies()
        self._post_counter = 0  # For require_opinion rotation
        self.metrics = {
            "cache_hits": 0, "cache_misses": 0, "generated": 0,
            "fallbacks": 0, "errors": 0, "retries": 0,
            "skipped_low_signal": 0,  # New: posts skipped for low signal
            "signal_passes": 0,       # New: posts that passed has_real_signal
        }
        logger.info("ContentEngine initialized (v2: compound signal validation)")

    def generate_reply(self, tweet_text: str, use_cache: bool = True, force_generation: bool = False) -> GenerationResult:
        try:
            # Step 1: Try cache
            cached = None
            if use_cache and not force_generation:
                cached = self.cache.get(tweet_text)
                if cached:
                    self.metrics["cache_hits"] += 1
                    return GenerationResult(
                        text=cached["reply"],
                        source=cached.get("source", "cache"),
                        quality_score=cached.get("quality_score", 0.5),
                        signal_density=self.moderator.signal_density(cached["reply"]),
                    )

            if not cached:
                self.metrics["cache_misses"] += 1

            # Step 2: Validate input
            is_valid, error = self.moderator.validate(tweet_text)
            if not is_valid:
                self.metrics["fallbacks"] += 1
                return GenerationResult(text=self._get_fallback(), source="fallback", quality_score=0.3, error=f"Input: {error}")

            # Step 3: Generate
            system_prompt = get_reply_system_prompt()
            generated_text = generate_contextual_reply(tweet_text=tweet_text, system_prompt=system_prompt)
            self.metrics["generated"] += 1

            # Step 4: Validate output
            is_valid, error = self.moderator.validate(generated_text)
            if not is_valid:
                self.metrics["fallbacks"] += 1
                return GenerationResult(text=self._get_fallback(), source="fallback", quality_score=0.3, error=f"Output: {error}")

            if self.moderator.is_generic(generated_text):
                self.metrics["fallbacks"] += 1
                return GenerationResult(text=self._get_fallback(), source="fallback", quality_score=0.3, error="Generic")

            # Step 5: Score + dedupe
            quality_score = self.moderator.score_quality(generated_text)
            signal = self.moderator.signal_density(generated_text)

            if self.moderator.is_duplicate(generated_text) or self.cache.is_duplicate_reply(generated_text):
                self.metrics["fallbacks"] += 1
                return GenerationResult(text=self._get_fallback(), source="fallback", quality_score=0.3, error="Duplicate")

            self.cache.set(tweet_text, generated_text, quality_score)
            return GenerationResult(text=generated_text, source="generated", quality_score=quality_score, signal_density=signal)

        except Exception as e:
            logger.error(f"Reply generation failed: {e}", exc_info=True)
            return GenerationResult(text=self._get_fallback(), source="fallback", quality_score=0.2, error=str(e))

    def generate_daily_tweet(self, topic: str = None, max_retries: int = 3) -> GenerationResult:
        """
        Generate a daily tweet with compound signal validation and mode-switching retries.

        Returns GenerationResult (not str) — caller can inspect:
        - result.text: the tweet
        - result.source: "generated", "retry_1", "retry_2", "retry_3", "fallback", "skip"
        - result.signal_density: 0.0–1.0
        - result.retries: how many retries were needed
        - result.error: reason if skipped or fallback

        If no tweet passes minimum signal threshold after all retries,
        returns GenerationResult with source="skip" and empty text.
        Caller should treat empty text as: do not post this slot.
        """
        now = datetime.now(timezone.utc)
        day_of_year = now.timetuple().tm_yday

        # Determine opinion rotation (require_opinion every 3rd post)
        self._post_counter += 1
        require_opinion = (self._post_counter % 3 == 0)

        # Get pillar and hook
        pillar = Config.get_content_pillar(day_of_year)
        hook = Config.get_viral_hook()

        logger.info(f"Daily tweet: pillar={pillar['name']}, hook={hook}, opinion={require_opinion}")

        seed = topic or _get_random_seed()
        best_tweet = None
        best_signal = 0.0
        retries_used = 0

        for attempt in range(max_retries + 1):
            # Build prompt — switch mode on retries
            if attempt == 0:
                system_prompt = get_daily_tweet_system_prompt(
                    pillar=pillar,
                    hook_format=hook,
                    require_opinion=require_opinion,
                )
                user_message = f"Write one original tweet about: {seed}"
            else:
                retries_used += 1
                self.metrics["retries"] += 1
                system_prompt = RetryStrategy.get_prompt(attempt, "", seed)
                user_message = seed
                logger.info(f"Retry {attempt}/{max_retries} — mode: {['', 'displacement', 'minimum_viable', 'fill_blank'][attempt]}")

            tweet = generate_contextual_reply(
                tweet_text=seed,
                system_prompt=system_prompt,
                user_message=user_message,
            )

            if not tweet or not tweet.strip():
                continue

            tweet = tweet.strip()

            # Gate 1: Basic moderation
            is_valid, error = self.moderator.validate(tweet)
            if not is_valid:
                logger.debug(f"Attempt {attempt}: moderation failed — {error}")
                continue

            # Gate 2: Generic check (was missing from daily tweet path before)
            if self.moderator.is_generic(tweet):
                logger.info(f"Attempt {attempt}: generic content — retrying")
                continue

            # Gate 3: Vague content check
            if is_vague_content(tweet):
                logger.info(f"Attempt {attempt}: vague content — retrying")
                # Store as best if it's the first attempt, but still retry
                if best_tweet is None:
                    best_tweet = tweet
                    best_signal = self.moderator.signal_density(tweet)
                continue

            # Gate 4: Compound signal check (strict)
            if has_real_signal(tweet):
                signal = self.moderator.signal_density(tweet)
                quality_score = self.moderator.score_quality(tweet)
                source = "generated" if attempt == 0 else f"retry_{attempt}"
                self.metrics["signal_passes"] += 1
                self.metrics["generated"] += 1

                # Use seed + first 20 chars of pattern as cache key for diversity
                cache_key = f"{seed[:50]}_{tweet[:20]}"
                self.cache.set(cache_key, tweet, quality_score)

                logger.info(f"✅ Tweet passed signal gate at attempt {attempt} (density={signal:.2f})")
                return GenerationResult(
                    text=tweet,
                    source=source,
                    quality_score=quality_score,
                    signal_density=signal,
                    retries=retries_used,
                )

            # Didn't pass signal gate but not vague — track as best effort
            signal = self.moderator.signal_density(tweet)
            if signal > best_signal:
                best_signal = signal
                best_tweet = tweet
            logger.info(f"Attempt {attempt}: no real signal (density={signal:.2f}) — retrying")

        # ── All retries exhausted ──────────────────────────────────
        # Only post best_tweet if it meets minimum signal threshold
        if best_tweet and best_signal >= MIN_FALLBACK_SIGNAL:
            quality_score = self.moderator.score_quality(best_tweet)
            self.metrics["fallbacks"] += 1
            logger.warning(f"Posting best-effort tweet (signal={best_signal:.2f}): {best_tweet[:60]}...")
            return GenerationResult(
                text=best_tweet,
                source="fallback_generated",
                quality_score=quality_score,
                signal_density=best_signal,
                retries=retries_used,
                error=f"Best effort (signal={best_signal:.2f}). Did not pass has_real_signal.",
            )

        # Signal too low — skip this post slot
        self.metrics["skipped_low_signal"] += 1
        logger.error(f"All {max_retries} attempts failed signal gate. Skipping post. Best signal: {best_signal:.2f}")
        return GenerationResult(
            text="",
            source="skip",
            quality_score=0.0,
            signal_density=best_signal,
            retries=retries_used,
            error=f"Skipped: signal={best_signal:.2f} below minimum {MIN_FALLBACK_SIGNAL}",
        )

    def generate_quote_text(self, tweet_text: str) -> str:
        system_prompt = get_quote_tweet_system_prompt()
        user_message = f"Write a short quote tweet commentary for this tweet:\n\n\"{tweet_text}\""
        text = generate_contextual_reply(tweet_text=tweet_text, system_prompt=system_prompt, user_message=user_message)
        return text.strip() if text else ""

    def generate_curiosity_reply(self, tweet_text: str) -> GenerationResult:
        try:
            system_prompt = get_curiosity_reply_prompt()
            generated_text = generate_contextual_reply(
                tweet_text=tweet_text,
                system_prompt=system_prompt,
                user_message=f'Reply to this tweet from someone who needs help:\n\n"{tweet_text}"'
            )
            is_valid, error = self.moderator.validate(generated_text)
            if not is_valid:
                return self.generate_reply(tweet_text)

            quality_score = self.moderator.score_quality(generated_text)
            signal = self.moderator.signal_density(generated_text)
            return GenerationResult(text=generated_text, source="curiosity", quality_score=quality_score, signal_density=signal)
        except Exception as e:
            logger.error(f"Curiosity reply failed: {e}")
            return self.generate_reply(tweet_text)

    def get_full_metrics(self) -> dict:
        """Extended metrics for observability."""
        base = self.cache.get_stats()
        base.update(self.metrics)
        total = self.metrics["signal_passes"] + self.metrics["skipped_low_signal"]
        base["signal_pass_rate"] = round(self.metrics["signal_passes"] / total, 2) if total > 0 else None
        base["opinion_rotation_counter"] = self._post_counter
        return base

    def _get_fallback(self) -> str:
        return random.choice(self.fallback_replies)

    # Backward compat
    def get_cache_stats(self) -> dict:
        return self.cache.get_stats()


_engine_instance: Optional[ContentEngine] = None


def get_content_engine() -> ContentEngine:
    global _engine_instance
    if _engine_instance is None:
        _engine_instance = ContentEngine()
    return _engine_instance
