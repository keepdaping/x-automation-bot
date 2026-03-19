"""
Content validation and quality scoring.

Added: signal_density() for measuring concrete information in tweets.
Expanded: is_generic() catches authority-killing vague content.
"""

import re
import hashlib
from typing import Optional, Tuple

from logger_setup import logger
from config import Config


# Tool names for signal detection
_SIGNAL_TOOLS = [
    "n8n", "zapier", "make", "gpt", "gpt-4", "gpt-4o", "claude", "chatgpt",
    "openai", "anthropic", "supabase", "vercel", "nextjs", "python",
    "playwright", "stripe", "notion", "perplexity", "cursor", "copilot",
    "langchain", "docker", "api", "webhook",
]

# Outcome verbs
_SIGNAL_OUTCOMES = [
    "broke", "fixed", "shipped", "built", "launched", "replaced", "saved",
    "lost", "earned", "charged", "paid", "cost", "dropped", "grew",
    "doubled", "automated", "crashed", "failed", "sold", "landed",
]

# Number patterns
_SIGNAL_NUMBERS = [
    r"\$\d+", r"\d+%", r"\d+x", r"\d+k",
    r"\d+\s*(?:hours?|hrs?|mins?|days?|weeks?|months?|years?)",
    r"\d+\s*(?:clients?|users?|runs?|calls?)",
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
        if not text or not isinstance(text, str):
            return False, "Reply is empty"

        if len(text) < cls.MIN_LENGTH:
            return False, f"Reply too short (min {cls.MIN_LENGTH} chars)"

        if len(text) > cls.MAX_LENGTH:
            return False, f"Reply too long ({len(text)} > {cls.MAX_LENGTH} chars)"

        for pattern in cls.BANNED_PATTERNS:
            if re.search(pattern, text, re.IGNORECASE):
                return False, f"Contains banned pattern: {pattern}"

        text_lower = text.lower()
        for word in Config.BANNED_WORDS:
            if word in text_lower:
                return False, f"Contains banned word: {word}"

        if text.count("!") > 2 or text.count("?") > 2:
            return False, "Excessive punctuation"

        if len(text) > 10 and text.isupper():
            return False, "All caps text"

        return True, None

    @classmethod
    def score_quality(cls, text: str) -> float:
        """Score content quality 0.0-1.0."""
        score = 0.5
        length = len(text)

        # Length scoring
        if 20 <= length <= 150:
            score += 0.15
        elif 150 < length <= 280:
            score += 0.10
        elif 10 <= length < 20:
            score += 0.05

        # Vocabulary diversity
        words = text.split()
        unique_words = len(set(w.lower() for w in words))
        if len(words) > 0:
            score += (unique_words / len(words)) * 0.10

        # Sentence count
        sentences = [s.strip() for s in re.split(r'[.!?]', text) if s.strip()]
        if 1 <= len(sentences) <= 3:
            score += 0.10

        # Not generic
        generic_phrases = [
            "i agree", "good point", "totally agree", "so true",
            "100%", "agreed", "yes", "yep", "ok",
        ]
        text_lower = text.lower()
        if not any(phrase in text_lower for phrase in generic_phrases):
            score += 0.10

        # Question presence
        if "?" in text:
            score += 0.10

        # Signal density bonus — new scoring dimension
        sig = cls.signal_density(text)
        score += sig * 0.15  # Up to 0.15 bonus for high-signal content

        # Stylistic markers
        if any(marker in text for marker in ["—", "'", "..."]):
            score += 0.05

        # Emoji control
        emoji_count = len(re.findall(r'[\U0001F300-\U0001F9FF]', text))
        if emoji_count <= 2:
            score += 0.05
        elif emoji_count > 3:
            score -= 0.15

        return min(1.0, max(0.0, score))

    @classmethod
    def signal_density(cls, text: str) -> float:
        """Measure how much concrete information a tweet contains.
        
        Returns 0.0-1.0:
            0.0 = no signals (pure opinion/vague)
            0.33 = one signal type
            0.67 = two signal types
            1.0 = all three signal types present
        
        Signal types:
            1. Tool mention (n8n, GPT-4, Zapier, etc.)
            2. Number with context ($50, 4 hours, 40%)
            3. Outcome verb (built, broke, shipped, earned, etc.)
        """
        text_lower = text.lower()
        signals = 0

        # Check tools
        for tool in _SIGNAL_TOOLS:
            if tool in text_lower:
                signals += 1
                break

        # Check numbers
        for pattern in _SIGNAL_NUMBERS:
            if re.search(pattern, text_lower):
                signals += 1
                break

        # Check outcome verbs
        for word in _SIGNAL_OUTCOMES:
            if re.search(rf"\b{word}\b", text_lower):
                signals += 1
                break

        return round(signals / 3.0, 2)

    @classmethod
    def is_generic(cls, text: str) -> bool:
        """Detect generic content that kills authority.
        
        Catches both low-effort replies AND vague motivational content.
        """
        text_lower = text.lower()

        # Low-effort reply patterns
        low_effort = [
            "i agree", "good point", "great point", "so true",
            "100%", "agreed", "yes", "yep", "ok", "interesting", "nice",
        ]
        if any(phrase in text_lower for phrase in low_effort):
            return True

        # Authority-killing vague patterns (new)
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
        ]
        if any(phrase in text_lower for phrase in vague_authority):
            return True

        return False

    @staticmethod
    def is_duplicate(text: str, db_path: str = None) -> bool:
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
