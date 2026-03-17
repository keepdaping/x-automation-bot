"""
Content validation and quality scoring.
Banned words are now configurable via Config.BANNED_WORDS.
"""

import re
import hashlib
from typing import Optional, Tuple

from logger_setup import logger
from config import Config


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
        score = 0.5
        length = len(text)

        if 20 <= length <= 150:
            score += 0.15
        elif 150 < length <= 280:
            score += 0.10
        elif 10 <= length < 20:
            score += 0.05

        words = text.split()
        unique_words = len(set(w.lower() for w in words))
        if len(words) > 0:
            score += (unique_words / len(words)) * 0.10

        sentences = [s.strip() for s in re.split(r'[.!?]', text) if s.strip()]
        if 1 <= len(sentences) <= 3:
            score += 0.10

        generic_phrases = [
            "i agree", "good point", "totally agree", "so true",
            "100%", "agreed", "yes", "yep", "ok",
        ]
        text_lower = text.lower()
        if not any(phrase in text_lower for phrase in generic_phrases):
            score += 0.10

        if "?" in text:
            score += 0.15

        vague_words = ["maybe", "probably", "might", "seem", "somewhat"]
        if not any(word in text_lower for word in vague_words):
            score += 0.05

        if any(marker in text for marker in ["—", "'", "..."]):
            score += 0.05

        emoji_count = len(re.findall(r'[\U0001F300-\U0001F9FF]', text))
        if emoji_count <= 2:
            score += 0.10
        elif emoji_count > 3:
            score -= 0.15

        return min(1.0, max(0.0, score))

    @classmethod
    def is_generic(cls, text: str) -> bool:
        text_lower = text.lower()
        generic_phrases = [
            "i agree", "good point", "great point", "so true",
            "100%", "agreed", "yes", "yep", "ok", "interesting", "nice",
        ]
        return any(phrase in text_lower for phrase in generic_phrases)

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
