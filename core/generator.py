# core/generator.py
import random
import time
from typing import Tuple
import anthropic
from anthropic import Anthropic

from config import Config
from logger_setup import log
from .moderator import is_duplicate, score_content_quality

_ai_draft_client: Anthropic | None = None
_ai_critique_client: Anthropic | None = None


def _get_draft_client() -> Anthropic:
    global _ai_draft_client
    if _ai_draft_client is None:
        _ai_draft_client = Anthropic(api_key=Config.ANTHROPIC_API_KEY)
    return _ai_draft_client


def _get_critique_client() -> Anthropic:
    global _ai_critique_client
    if _ai_critique_client is None:
        _ai_critique_client = Anthropic(api_key=Config.ANTHROPIC_API_KEY)
    return _ai_critique_client


_SYSTEM_BASE = """You are a 24-year-old self-taught developer documenting the journey of escaping the 9-5 using AI tools, freelancing, side projects and automation.

Voice rules:
- Casual, honest, relatable — like texting a friend
- Show struggles + small wins, not just polished success
- Anti-corporate, anti-LinkedIn tone
- Never robotic, never buzzwords (leverage, synergy, bandwidth, etc.)
- Max 1 emoji, max 1 relevant hashtag
- NEVER start with: "I", "Nobody tells you", "Consistency is", "Here's the thing", "Unpopular opinion"

Audience: 18–30 year olds learning to code, trying to make money online, escaping traditional jobs.

Today is {weekday}. Adjust tone accordingly:
- Monday–Thursday → energetic, actionable, forward-looking
- Friday–Sunday → reflective, honest, lessons-learned

Output ONLY the tweet text — no labels, no quotes, no explanations.
Max 275 characters."""

_FORMAT_INSTRUCTIONS = {
    "HOOK_STORY": """Start with a strong hook (question, hard truth, "True story:", "The awkward part is…"). Tell a short personal story (3–6 lines). End with punchy takeaway or open question.""",
    "QUOTE_STYLE": """1–3 sharp, quotable lines. Minimal fluff. High screenshot value. Can start with "Hard truth:" or "Most people…" if natural.""",
    "QUESTION_LIST": """Strong opening question. Then 3–5 short bullet-style points or numbered insights. End with call-to-reflection or related question.""",
    "THREAD": """This will become first tweet of a thread. Write strong hook + story opener + promise of value in next tweets. End with cliffhanger or transition."""
}


def generate_post(topic: str, fmt: str) -> Tuple[str, str, float]:
    """Generate → critique → (possibly rewrite) → final tweet"""
    weekday = time.strftime("%A")

    system = _SYSTEM_BASE.format(weekday=weekday)
    system += "\n\n" + _FORMAT_INSTRUCTIONS.get(fmt, _FORMAT_INSTRUCTIONS["HOOK_STORY"])

    draft_client = _get_draft_client()

    for attempt in range(1, Config.AI_MAX_RETRIES + 1):
        try:
            # Step 1: fast draft (Haiku)
            draft_msg = draft_client.messages.create(
                model=Config.AI_MODEL_DRAFT,
                max_tokens=Config.AI_MAX_TOKENS,
                system=system,
                messages=[{"role": "user", "content": f"Topic: {topic}"}]
            )
            draft = draft_msg.content[0].text.strip()

            if not draft or len(draft) > 280:
                log.warning(f"Draft attempt {attempt} invalid length — retrying")
                continue

            # Step 2: critique & score (Sonnet)
            critique = _get_critique_client().messages.create(
                model=Config.AI_MODEL_CRITIQUE,
                max_tokens=120,
                system="""You are a brutally honest X growth consultant.
Rate this tweet 1–10 for:
- Hook strength (does it stop scroll?)
- Relatability / emotional pull
- Reply / quote potential
- Clarity & rhythm
Overall score only if ≥8.5 — otherwise explain why and suggest fixes.""",
                messages=[{"role": "user", "content": f"Rate & improve if needed:\n\n{draft}"}]
            )
            critique_text = critique.content[0].text.strip()

            score = score_content_quality(critique_text)
            log.info(f"Attempt {attempt} — draft score ≈ {score:.1f}")

            if score >= 8.5 and not is_duplicate(draft):
                return draft, "ai", score

            # Step 3: rewrite attempt
            rewrite_prompt = f"Rewrite this tweet to reach at least 8.5/10 quality:\nOriginal:\n{draft}\n\nCritique:\n{critique_text}"
            rewrite_msg = _get_critique_client().messages.create(
                model=Config.AI_MODEL_CRITIQUE,
                max_tokens=Config.AI_MAX_TOKENS,
                system=system,
                messages=[{"role": "user", "content": rewrite_prompt}]
            )
            final = rewrite_msg.content[0].text.strip()

            if len(final) <= 280 and not is_duplicate(final):
                final_score = score_content_quality(final)
                return final, "ai-rewritten", final_score

            time.sleep(1.5 ** attempt)

        except Exception as e:
            log.error(f"Generation error (attempt {attempt}): {e}")
            if attempt == Config.AI_MAX_RETRIES:
                break

    # Fallback
    from .fallback import FALLBACK_POSTS
    fb = random.choice(FALLBACK_POSTS)
    return fb, "fallback", 7.0