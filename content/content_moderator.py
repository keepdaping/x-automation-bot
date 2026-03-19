"""
Content validation and quality scoring.

CHANGES FROM PREVIOUS VERSION:
1. signal_density() — implication bucket now requires STRONG phrases only
   (removes "now", "yet", "means", "somehow" which were filler, not signals)
2. score_quality() — length bonus flattened; signal density carries real weight
3. has_strong_ending() — new method, checks last line specifically
4. is_generic() — expanded with ending-specific weak phrases
5. NICHE_TOOL_SIGNALS deduped with engine.py's KNOWN_TOOLS list
"""

import re
import hashlib
from typing import Optional, Tuple

from logger_setup import logger
from config import Config


# ── Tool list (keep in sync with engine.py KNOWN_TOOLS) ────────────────────
_SIGNAL_TOOLS = [
    "n8n", "zapier", "make", "gpt", "gpt-4", "gpt-4o", "claude", "chatgpt",
    "openai", "anthropic", "supabase", "vercel", "nextjs", "next.js",
    "python", "playwright", "stripe", "notion", "airtable", "perplexity",
    "midjourney", "cursor", "github", "copilot", "langchain", "replicate",
    "huggingface", "firebase", "railway", "render", "docker",
    "postgres", "redis", "sqlite", "api", "webhook", "cron", "make.com",
]

# ── Outcome verbs ────────────────────────────────────────────────────────────
_SIGNAL_OUTCOMES = [
    "broke", "fixed", "shipped", "built", "launched", "replaced", "saved",
    "lost", "earned", "charged", "paid", "cost", "dropped", "grew",
    "doubled", "tripled", "automated", "hired", "fired", "quit", "switched",
    "migrated", "deployed", "crashed", "failed", "sold", "closed", "landed",
    "deleted", "eliminated", "compressed", "reduced", "killed",
]

# ── Strong implication phrases ONLY ─────────────────────────────────────────
# Removed: "now", "yet", "means", "somehow", "worse", "overnight" (too broad)
# Kept/added: specific phrases that require intentional use
_SIGNAL_IMPLICATIONS = [
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

# ── Number patterns ──────────────────────────────────────────────────────────
_SIGNAL_NUMBERS = [
    r"\$\d+",
    r"\d+%",
    r"\d+x",
    r"\d+k",
    r"\d+\s*(?:hours?|hrs?|mins?|days?|weeks?|months?|years?)",
    r"\d+\s*(?:clients?|users?|runs?|calls?|people|devs?)",
    r"\d+/(?:month|week|day|run|year|hr|hour)",
]

# ── Named roles (for ending strength check) ──────────────────────────────────
_ROLE_SIGNALS = [
    "va", "virtual assistant", "junior", "senior", "mid-level",
    "freelancer", "contractor", "developer", "recruiter", "bookkeeper",
    "cfo", "manager", "team", "client", "employee", "analyst",
    "researcher", "writer", "copywriter", "ops", "sales rep",
]

# ── Weak ending phrases ──────────────────────────────────────────────────────
_WEAK_ENDINGS = [
    "the tools are there",
    "adapt or get left behind",
    "that's the reality",
    "this is the world we live in",
    "things are changing",
    "just something to think about",
    "make of that what you will",
    "the future is here",
    "it is what it is",
    "time will tell",
    "changed everything",
    "and it works",
    "dropped overnight",       # too vague — who dropped? what dropped?
    "everyone knows this",
    "it's only going to get",
    "we'll see what happens",
    "interesting times",
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
            return False, "Empty"

        if len(text) < cls.MIN_LENGTH:
            return False, f"Too short (min {cls.MIN_LENGTH})"

        if len(text) > cls.MAX_LENGTH:
            return False, f"Too long ({len(text)} > {cls.MAX_LENGTH})"

        for pattern in cls.BANNED_PATTERNS:
            if re.search(pattern, text, re.IGNORECASE):
                return False, f"Banned pattern: {pattern}"

        text_lower = text.lower()
        for word in Config.BANNED_WORDS:
            if word in text_lower:
                return False, f"Banned word: {word}"

        if text.count("!") > 2 or text.count("?") > 2:
            return False, "Excessive punctuation"

        if len(text) > 10 and text.isupper():
            return False, "All caps"

        return True, None

    @classmethod
    def score_quality(cls, text: str) -> float:
        """
        REDESIGNED:
        - Length bonus flattened (was over-rewarding short motivational tweets)
        - Signal density carries the real weight (up to 0.25 bonus)
        - Strong ending adds 0.10 bonus
        - Vague ending subtracts 0.10
        - Vocabulary diversity weight reduced (was rewarding list tweets)
        """
        score = 0.5
        text_lower = text.lower()

        # ── Length: flat bonus for any reasonable length ──────────
        if 30 <= len(text) <= 280:
            score += 0.05

        # ── Vocabulary diversity (reduced weight) ─────────────────
        words = text.split()
        unique_words = len(set(w.lower() for w in words))
        if len(words) > 0:
            score += (unique_words / len(words)) * 0.06

        # ── Sentence structure ─────────────────────────────────────
        sentences = [s.strip() for s in re.split(r'[.!?]', text) if s.strip()]
        if 1 <= len(sentences) <= 4:
            score += 0.07

        # ── Not generic ────────────────────────────────────────────
        generic_phrases = ["i agree", "good point", "totally agree", "so true", "100%", "agreed"]
        if not any(phrase in text_lower for phrase in generic_phrases):
            score += 0.06

        # ── Question presence (reply trigger) ─────────────────────
        if "?" in text:
            score += 0.10

        # ── Signal density (main quality driver) ──────────────────
        sig = cls.signal_density(text)
        score += sig * 0.25  # Up to 0.25 for high-signal content

        # ── Ending strength ────────────────────────────────────────
        if cls.has_strong_ending(text):
            score += 0.10
        elif cls._has_weak_ending(text):
            score -= 0.10

        # ── Stylistic markers ──────────────────────────────────────
        if any(m in text for m in ["—", "'"]):
            score += 0.03

        # ── Emoji: excessive penalty only ─────────────────────────
        emoji_count = len(re.findall(r'[\U0001F300-\U0001F9FF]', text))
        if emoji_count > 2:
            score -= 0.10

        return min(1.0, max(0.0, score))

    @classmethod
    def signal_density(cls, text: str) -> float:
        """
        Measure how much concrete information a tweet contains.

        Returns 0.0–1.0.
        Four buckets: tool, number, outcome, strong implication.
        Each worth 0.25.

        CHANGE: Implication bucket now requires STRONG phrases only.
        "now", "yet", "means", "somehow" are NOT counted — they appear
        in virtually all English sentences and inflate scores falsely.
        """
        text_lower = text.lower()
        signals = 0

        # Tool mention
        if any(tool in text_lower for tool in _SIGNAL_TOOLS):
            signals += 1

        # Number with context
        if any(re.search(p, text_lower) for p in _SIGNAL_NUMBERS):
            signals += 1

        # Outcome verb
        if any(re.search(rf"\b{w}\b", text_lower) for w in _SIGNAL_OUTCOMES):
            signals += 1

        # Strong implication only
        if any(phrase in text_lower for phrase in _SIGNAL_IMPLICATIONS):
            signals += 1

        return round(signals / 4.0, 2)

    @classmethod
    def has_strong_ending(cls, text: str) -> bool:
        """
        NEW: Check that the last line of a tweet does real work.

        A strong ending must do at least one of:
        - Name a specific role or person
        - Contain a number or dollar amount
        - Ask a question
        - Contain a strong implication phrase
        - State a position or rule

        Does NOT count:
        - Vague observations ("things are changing")
        - Soft closures ("it is what it is")
        """
        lines = [l.strip() for l in text.strip().split('\n') if l.strip()]
        if not lines:
            return False
        last = lines[-1].lower()

        # Weak ending — immediately return False
        if cls._has_weak_ending(text):
            return False

        # Strong: named role
        if any(role in last for role in _ROLE_SIGNALS):
            return True

        # Strong: number in last line
        if any(re.search(p, last) for p in _SIGNAL_NUMBERS):
            return True

        # Strong: question
        if "?" in last:
            return True

        # Strong: implication phrase
        if any(phrase in last for phrase in _SIGNAL_IMPLICATIONS):
            return True

        # Strong: outcome verb
        if any(re.search(rf"\b{w}\b", last) for w in _SIGNAL_OUTCOMES):
            return True

        return False

    @classmethod
    def _has_weak_ending(cls, text: str) -> bool:
        lines = [l.strip() for l in text.strip().split('\n') if l.strip()]
        if not lines:
            return False
        last = lines[-1].lower()
        return any(phrase in last for phrase in _WEAK_ENDINGS)

    @classmethod
    def is_generic(cls, text: str) -> bool:
        """
        EXPANDED: Catches low-effort replies, motivational filler, AND
        weak ending patterns that look finished but aren't.
        """
        text_lower = text.lower()

        # Low-effort reply patterns
        low_effort = [
            "i agree", "good point", "great point", "so true",
            "100%", "agreed", "yes", "yep", "ok", "interesting", "nice",
        ]
        if any(phrase in text_lower for phrase in low_effort):
            return True

        # Authority-killing vague patterns
        vague_authority = [
            "stop overthinking and start",
            "consistency is the only",
            "just ship it",
            "done is better than perfect",
            "the secret is",
            "work smarter not harder",
            "hustle culture",
            "unlock your potential",
            "automation is the future",
            "ai will change everything",
            "the future is here",
            "adapt or die",
            "learn to code",
            "trust the process",
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
