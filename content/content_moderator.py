"""
Content validation and quality scoring.

Ensures generated replies meet quality standards before posting.
"""

import re
import hashlib
from typing import Optional, Tuple

from logger_setup import logger


class ContentModerator:
    """Validates and scores content quality."""

    # Banned patterns and words
    BANNED_PATTERNS = [
        r"(?:https?://|www\.)\S+",  # URLs
        r"[#@]\w+",  # Hashtags and @mentions (to avoid spam look)
        r"(?:click|subscribe|follow)\s+(?:below|here|link)",  # CTAs
        r"(?:dm|message)\s+(?:me|us|for)",  # DM spam
        r"(?:limited|exclusive)\s+(?:offer|deal|access)",  # Spam language
        r"i'?m\s+(?:a\s+)?(?:ai|bot|artificial)",  # "I'm a bot/AI" revelations (lowercase)
    ]

    # Only ban obvious spam/scam words, not legitimate topic words
    BANNED_WORDS = [
        # Crypto/gambling spam
        "crypto", "nft", "bitcoin", "eth", "casino", "poker", "betting",
        # Explicit spam
        "viagra", "cialis", "pharmacy",
        # MLM spam
        "mlm", "pyramid", "dropship",
    ]

    MIN_LENGTH = 3  # Minimum reply length (characters)
    MAX_LENGTH = 280  # Twitter character limit
    
    @classmethod
    def validate(cls, text: str) -> Tuple[bool, Optional[str]]:
        """
        Validate reply content.
        
        Args:
            text: Reply text to validate
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        if not text or not isinstance(text, str):
            return False, "Reply is empty"

        # Length check
        if len(text) < cls.MIN_LENGTH:
            return False, f"Reply too short (min {cls.MIN_LENGTH} chars)"
        
        if len(text) > cls.MAX_LENGTH:
            return False, f"Reply too long ({len(text)} > {cls.MAX_LENGTH} chars)"

        # Check for banned patterns (URLs, CTAs, etc.)
        for pattern in cls.BANNED_PATTERNS:
            if re.search(pattern, text, re.IGNORECASE):
                return False, f"Contains banned pattern: {pattern}"

        # Check for banned words
        text_lower = text.lower()
        for word in cls.BANNED_WORDS:
            if word in text_lower:
                return False, f"Contains banned word: {word}"

        # Check for excessive punctuation (spam indicator)
        if text.count("!") > 2 or text.count("?") > 2:
            return False, "Excessive punctuation"

        # Check for all caps (spam indicator)
        if len(text) > 10 and text.isupper():
            return False, "All caps text (looks like spam)"

        return True, None

    @classmethod
    def score_quality(cls, text: str) -> float:
        """
        Score content quality on 0-1 scale.
        
        Higher scores = higher quality. Used for ranking cached replies.
        
        Args:
            text: Reply text to score
            
        Returns:
            Quality score (0.0 - 1.0)
        """
        score = 0.5  # Start at neutral

        # Length bonus (sweet spot 20-150 chars)
        length = len(text)
        if 20 <= length <= 150:
            score += 0.15
        elif 150 < length <= 280:
            score += 0.10
        elif 10 <= length < 20:
            score += 0.05

        # Word variety (more diverse language)
        words = text.split()
        unique_words = len(set(w.lower() for w in words))
        if len(words) > 0:
            diversity = unique_words / len(words)
            score += diversity * 0.10  # Max 0.10 bonus

        # Sentence structure (complete sentences are better)
        sentences = [s.strip() for s in re.split(r'[.!?]', text) if s.strip()]
        if 1 <= len(sentences) <= 3:
            score += 0.10
        elif len(sentences) > 3:
            score += 0.05

        # Avoid generic phrases
        generic_phrases = [
            "i agree", "good point", "totally agree", "so true",
            "100%", "agreed", "yes", "yep", "ok",
        ]
        text_lower = text.lower()
        if not any(phrase in text_lower for phrase in generic_phrases):
            score += 0.10

        # Questions are engaging
        if "?" in text:
            score += 0.15

        # Specific, concrete language (no vague hedging)
        vague_words = ["maybe", "probably", "might", "seem", "somewhat"]
        if not any(word in text_lower for word in vague_words):
            score += 0.05

        # Personality markers (genuine voice)
        if any(marker in text for marker in ["—", "'", "..."]):
            score += 0.05

        # Avoid emoji overload (none or 1-2 is good)
        emoji_count = len(re.findall(r'[\U0001F300-\U0001F9FF]', text))
        if emoji_count == 0 or emoji_count <= 2:
            score += 0.10
        elif emoji_count > 3:
            score -= 0.15

        # Clamp score to 0-1 range
        return min(1.0, max(0.0, score))

    @classmethod
    def is_generic(cls, text: str) -> bool:
        """Check whether a reply is too generic or templated."""
        text_lower = text.lower()
        generic_phrases = [
            "i agree",
            "good point",
            "great point",
            "so true",
            "100%",
            "agreed",
            "yes",
            "yep",
            "ok",
            "interesting",
            "nice",
        ]
        return any(phrase in text_lower for phrase in generic_phrases)

    @staticmethod
    def is_duplicate(text: str, db_path: str = "data/bot.db") -> bool:
        """
        Check if reply is duplicate of previous replies.
        
        Args:
            text: Reply text to check
            db_path: Path to database
            
        Returns:
            True if similar reply exists, False otherwise
        """
        import sqlite3
        
        try:
            text_hash = hashlib.sha256(text.strip().lower().encode()).hexdigest()
            
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            # Check exact match
            cursor.execute(
                "SELECT COUNT(*) FROM replies WHERE text_hash = ?",
                (text_hash,)
            )
            
            result = cursor.fetchone()[0]
            conn.close()
            
            return result > 0
            
        except Exception as e:
            logger.warning(f"Duplicate check failed: {e}")
            return False
