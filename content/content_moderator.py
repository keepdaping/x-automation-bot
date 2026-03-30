"""
Content validation and quality scoring.

Improved:
- signal_density now requires anchor (tool/number) + consequence
- Added has_named_role() for specificity
- Added has_strong_ending() for punchy endings
- Better emoji scoring (rewards 1 emoji, penalizes >2)
- Logging in validation methods for debuggability
"""

import re
import hashlib
from typing import Optional, Tuple

from logger_setup import logger
from config import Config


# Tool names for signal detection (expanded for your niche)
_SIGNAL_TOOLS = [
    "n8n", "zapier", "make", "gpt", "gpt-4", "gpt-4o", "claude", "chatgpt",
    "openai", "anthropic", "supabase", "vercel", "nextjs", "next.js",
    "python", "playwright", "stripe", "notion", "airtable", "perplexity",
    "midjourney", "cursor", "github", "copilot", "langchain", "replicate",
    "huggingface", "firebase", "railway", "render", "fly.io", "docker",
    "postgres", "redis", "sqlite", "api", "webhook", "cron",
]

# Outcome verbs — concrete actions/changes
_SIGNAL_OUTCOMES = [
    "broke", "fixed", "shipped", "built", "launched", "replaced", "saved",
    "lost", "earned", "charged", "paid", "cost", "dropped", "grew",
    "doubled", "tripled", "killed", "automated", "hired", "fired",
    "quit", "switched", "migrated", "deployed", "crashed", "failed",
    "sold", "closed", "landed", "signed", "handled", "solved", "cut",
]

# Strong implication/consequence phrases — specific stakes, not filler
_SIGNAL_IMPLICATIONS = [
    "doesn't know yet", "still on retainer", "won't last", "for now",
    "this is how it starts", "gets cheaper", "changes what",
    "nobody got fired", "the job didn't disappear", "they don't know",
    "asked why they're still", "what happens when",
    "that's somehow worse", "nobody talks about the part",
    "the math is brutal", "they only see the cost",
    "the VA caught things", "client doesn't know",
    "nobody's had that conversation", "the junior still",
    "CFO asked", "recruiter doesn't know", "bookkeeper still employed",
    "team is exhausted", "personal touch is gone",
    "nobody knows how to fix", "they think i'm doing it manually",
]

# Number patterns (contextual)
_SIGNAL_NUMBERS = [
    r"\$\d+", r"\d+%", r"\d+x", r"\d+k",
    r"\d+\s*(?:hours?|hrs?|mins?|minutes?|days?|weeks?|months?|years?)",
    r"\d+\s*(?:clients?|users?|runs?|calls?|people|devs?)",
]

# Named roles — forces specificity (critical for engagement)
NAMED_ROLES = [
    "va", "virtual assistant", "junior", "senior", "mid-level",
    "freelancer", "contractor", "developer", "recruiter", "bookkeeper",
    "cfo", "manager", "team", "client", "employee", "analyst",
    "founder", "startup", "ceo", "co-founder",
]

# Weak endings — endings that lack tension/punch
WEAK_ENDINGS = [
    "the tools are there", "adapt or get left behind",
    "that's the reality", "this is the world we live in",
    "things are changing", "just something to think about",
    "make of that what you will", "the future is here",
    "it is what it is", "time will tell",
    "dropped overnight", "changed everything", "and it works",
    "the value dropped", "it got cheaper",
]


class ContentModerator:
    """Validates and scores content quality."""

    BANNED_PATTERNS = [
        r"(?:https?://|www\.)\S+",
        r"[#@]\w+",
        r"(?:click|subscribe|follow)\s+(?:below|here|link)",
        r"(?:dm|message)\s+(?:me|us|for)",
        r"(?:limited|exclusive)\s+(?:offer|deal|access)",
        r"i'?m\s+(?:a\s+)?(?:ai|bot|artificial)",
    ]

    MIN_LENGTH = 3
    MAX_LENGTH = 280

    @classmethod
    def validate(cls, text: str) -> Tuple[bool, Optional[str]]:
        """Basic content validation — returns (is_valid, error_message)"""
        if not text or not isinstance(text, str):
            return False, "Reply is empty"

        text = text.strip()
        if len(text) < cls.MIN_LENGTH:
            return False, f"Reply too short (min {cls.MIN_LENGTH} chars)"

        if len(text) > cls.MAX_LENGTH:
            return False, f"Reply too long ({len(text)} > {cls.MAX_LENGTH} chars)"

        # Check banned patterns
        for pattern in cls.BANNED_PATTERNS:
            if re.search(pattern, text, re.IGNORECASE):
                logger.debug(f"Validation failed: banned pattern {pattern}")
                return False, f"Contains banned pattern: {pattern}"

        # Check banned words from config
        text_lower = text.lower()
        for word in Config.BANNED_WORDS:
            if word in text_lower:
                logger.debug(f"Validation failed: banned word {word}")
                return False, f"Contains banned word: {word}"

        # Punctuation / style checks
        if text.count("!") > 3 or text.count("?") > 3:
            logger.debug("Validation failed: excessive punctuation")
            return False, "Excessive punctuation"

        if len(text) > 15 and text.isupper():
            logger.debug("Validation failed: all caps text")
            return False, "All caps text"

        return True, None

    @classmethod
    def score_quality(cls, text: str) -> float:
        """Score content quality 0.0-1.0 (higher = better)."""
        score = 0.5
        length = len(text.strip())

        # Length sweet spot (longer rewarded more for depth)
        if 40 <= length <= 180:
            score += 0.20
        elif 180 < length <= 280:
            score += 0.15
        elif 20 <= length < 40:
            score += 0.08

        # Vocabulary diversity
        words = [w.lower() for w in text.split() if len(w) > 2]
        if words:
            unique_ratio = len(set(words)) / len(words)
            score += unique_ratio * 0.12

        # Sentence / line variety
        sentences = [s.strip() for s in re.split(r'[.!?]', text) if s.strip()]
        if 1 <= len(sentences) <= 4:
            score += 0.12

        # Not generic / low-effort
        if not cls.is_generic(text):
            score += 0.15

        # Question or curiosity presence
        if "?" in text or "..." in text:
            score += 0.08

        # Signal density bonus (biggest weight)
        sig = cls.signal_density(text)
        score += sig * 0.25  # up to +0.25 for high-signal content

        # Named role bonus
        if cls.has_named_role(text):
            score += 0.10

        # Strong ending bonus
        if cls.has_strong_ending(text):
            score += 0.12
        elif any(weak in text.lower() for weak in WEAK_ENDINGS):
            score -= 0.10

        # Stylistic markers (em-dash, ellipsis, personality)
        if any(marker in text for marker in ["—", "…", "lol", "tbh"]):
            score += 0.05

        # Emoji control (reward 1 emoji, penalize >2)
        emoji_count = len(re.findall(r'[\U0001F300-\U0001F9FF]', text))
        if emoji_count == 1:
            score += 0.05
        elif emoji_count == 0:
            score += 0.02  # slight bonus for restraint
        elif emoji_count > 2:
            score -= 0.12

        return min(1.0, max(0.0, round(score, 2)))

    @classmethod
    def signal_density(cls, text: str) -> float:
        """Measure concrete information density (0.0-1.0)."""
        text_lower = text.lower()
        signals = 0

        # 1. Tool mention
        if any(tool in text_lower for tool in _SIGNAL_TOOLS):
            signals += 1

        # 2. Number with context
        if any(re.search(pattern, text_lower) for pattern in _SIGNAL_NUMBERS):
            signals += 1

        # 3. Outcome verb
        if any(re.search(rf"\b{word}\b", text_lower) for word in _SIGNAL_OUTCOMES):
            signals += 1

        # 4. Strong implication/consequence
        if any(phrase in text_lower for phrase in _SIGNAL_IMPLICATIONS):
            signals += 1

        return round(signals / 4.0, 2)

    @classmethod
    def has_named_role(cls, text: str) -> bool:
        """Check if tweet names a specific role (VA, junior, CFO, etc.)."""
        text_lower = text.lower()
        return any(role in text_lower for role in NAMED_ROLES)

    @classmethod
    def has_strong_ending(cls, text: str) -> bool:
        """Check if last line creates tension/punch."""
        lines = [l.strip() for l in text.split('\n') if l.strip()]
        if not lines:
            return False
        last = lines[-1].lower()

        # Must do one of: question, named role, strong implication, number
        return (
            "?" in last or
            any(role in last for role in NAMED_ROLES) or
            any(phrase in last for phrase in _SIGNAL_IMPLICATIONS) or
            any(re.search(pattern, last) for pattern in _SIGNAL_NUMBERS)
        )

    @classmethod
    def is_generic(cls, text: str) -> bool:
        """Detect generic, low-authority content that kills engagement."""
        text_lower = text.lower()

        # Multi-word phrases are specific enough to match at any length.
        low_effort_phrases = [
            "i agree", "good point", "great point", "so true",
        ]
        if any(phrase in text_lower for phrase in low_effort_phrases):
            return True

        # Single tokens are only reliable low-effort signals in very short text
        # (≤ 40 chars). In longer tweets these tokens appear in legitimate context,
        # e.g. "100% of the VAs I know still export data manually" is not generic.
        low_effort_tokens = [
            "100%", "agreed", "yes", "yep", "ok", "interesting", "nice",
            "fair", "true", "facts", "real", "relatable",
        ]
        if len(text.strip()) <= 40 and any(token in text_lower for token in low_effort_tokens):
            return True

        # Vague motivational / authority-killing patterns
        vague_authority = [
            "stop overthinking and start",
            "consistency is the only",
            "just ship it",
            "done is better than perfect",
            "the secret is",
            "work smarter not harder",
            "hustle culture",
            "grind mindset",
            "unlock your potential",
            "automation is the future",
            "ai will change everything",
            "the future is here",
            "adapt or die",
            "learn to code",
            "trust the process",
            "most people don't realize",
            "everyone says this but",
            "the real problem is people",
        ]
        if any(phrase in text_lower for phrase in vague_authority):
            return True

        return False

    @staticmethod
    def is_duplicate(text: str, db_path: str = None) -> bool:
        """Check if this exact text already exists in replies table."""
        import sqlite3
        if db_path is None:
            db_path = Config.DATABASE_PATH
        try:
            text_hash = hashlib.sha256(text.strip().lower().encode()).hexdigest()
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM replies WHERE text_hash = ?", (text_hash,))
            result = cursor.fetchone()[0]
            conn.close()
            return result > 0
        except Exception as e:
            logger.warning(f"Duplicate check failed: {e}")
            return False