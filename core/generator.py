# core/generator.py

import random
import time
from typing import Tuple

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

_SYSTEM_BASE = """
You are a 24-year-old self-taught developer documenting the journey of escaping the 9-5 using AI tools, freelancing, side projects and automation.

Voice rules:

* casual and human
* honest and relatable
* show struggles + small wins
* anti corporate tone
* never robotic
* avoid buzzwords (leverage, synergy, bandwidth)

Style rules:

* strong hook in first line
* conversational rhythm
* maximum 1 emoji
* maximum 1 hashtag
* 275 characters max

Audience:
18–30 year olds learning to code, freelancing, trying to escape traditional jobs.

Output ONLY the tweet text.
"""

_FORMAT_INSTRUCTIONS = {
"HOOK_STORY": """
Start with a strong hook.
Tell a short personal experience.
End with a lesson or insight.
""",
"QUOTE_STYLE": """
1–3 punchy lines.
High screenshot value.
Should feel quotable.
""",
"QUESTION_LIST": """
Start with a question.
Give 3–4 quick insights.
End with a reflection question.
""",
"THREAD": """
Write the first tweet of a thread.
Strong hook + curiosity.
Promise value in the next tweets.
"""
}

def generate_post(topic: str, fmt: str) -> Tuple[str, str, float]:
    system = _SYSTEM_BASE + "\n\n" + _FORMAT_INSTRUCTIONS.get(fmt, "")
    draft_client = _get_draft_client()

    for attempt in range(1, Config.AI_MAX_RETRIES + 1):
        try:
            draft_msg = draft_client.messages.create(
                model=Config.AI_MODEL_DRAFT,
                max_tokens=Config.AI_MAX_TOKENS,
                system=system,
                messages=[{
                    "role": "user",
                    "content": f"""Topic: {topic}

Write a tweet based on:

* personal struggle
* small wins
* lessons learned
* things beginners misunderstand
"""
                }]
            )

            draft = draft_msg.content[0].text.strip()

            if not draft or len(draft) > 280:
                log.warning("Draft invalid length — retrying")
                continue

            critique = _get_critique_client().messages.create(
                model=Config.AI_MODEL_CRITIQUE,
                max_tokens=200,
                system="""You are a brutally honest X growth consultant.

Rate this tweet 1–10 for:

* hook
* relatability
* emotional trigger
* quote tweet potential
* screenshot potential
* clarity

Output:
Score: X/10
Then explain briefly why.
""",
                messages=[{"role": "user", "content": draft}]
            )

            critique_text = critique.content[0].text.strip()

            score = score_content_quality(critique_text)
            log.info(f"Attempt {attempt} — score ≈ {score:.1f}")

            if score >= 7.8 and not is_duplicate(draft):
                return draft, "ai", score

            rewrite_prompt = f"""Rewrite this tweet to improve engagement.

Original tweet:
{draft}

Critique:
{critique_text}

Improve hook and relatability.
"""

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

    FALLBACK_POSTS = [
        "Most people wait until they're ready. Ready never comes. Ship it.",
        "Clients don't pay for code. They pay for solved problems.",
        "AI won't take your job. Someone using AI will.",
        "Building things beats consuming tutorials.",
        "Your first project won't be perfect. It just needs to exist.",
        "Debugging at 2am builds character.",
    ]

    fb = random.choice(FALLBACK_POSTS)
    return fb, "fallback", 7.0

def generate_contextual_reply(tweet_text: str) -> str:
    """Generate contextual reply to a tweet"""
    try:
        client = _get_draft_client()

        prompt = f"""Reply naturally to this tweet.

Tweet:
{tweet_text}

Rules:

* conversational tone
* short reply
* no hashtags
* no emojis
"""

        resp = client.messages.create(
            model=Config.AI_MODEL_DRAFT,
            max_tokens=80,
            messages=[{"role": "user", "content": prompt}]
        )

        return resp.content[0].text.strip()

    except Exception as e:
        log.error(f"Reply generation failed: {e}")
        return random.choice([
            "Interesting perspective.",
            "That's a good point.",
            "I hadn't thought about it that way.",
            "Makes sense."
        ])


def generate_reply(tweet_text: str) -> str:
    """Generate a reply to a tweet"""
    return generate_contextual_reply(tweet_text)
