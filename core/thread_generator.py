# core/thread_generator.py
import time
import random
import anthropic
from typing import List, Optional

from config import Config
from logger_setup import log
from .generator import _get_critique_client   # Reuse existing client factory


def generate_thread(topic: str) -> Optional[List[str]]:
    """
    Generate a 4-tweet thread using the critique model (better coherence).
    Returns list of 4 strings or None on failure.
    """
    client = _get_critique_client()  # Reuse the global Sonnet client

    weekday = time.strftime("%A")

    system_prompt = f"""\
{_SYSTEM_BASE.format(weekday=weekday)}

This is a **4-tweet thread** about: {topic}

Rules:
- Tweet 1: strong hook + context + promise of value (1/4)
- Tweet 2–3: continue the story / list insights / build tension
- Tweet 4: strong close, takeaway, open question or call to reflect
- Number each tweet explicitly: "1/4", "2/4", etc. at the start
- Keep each tweet under 275 characters
- Casual, honest, relatable voice — no corporate buzzwords
- Output **exactly** 4 lines separated by --- (no extra text)
"""

    try:
        msg = client.messages.create(
            model=Config.AI_MODEL_CRITIQUE,  # Sonnet for better thread coherence
            max_tokens=800,
            system=system_prompt,
            messages=[{"role": "user", "content": f"Generate 4-tweet thread on: {topic}"}]
        )

        content = msg.content[0].text.strip()
        parts = [p.strip() for p in content.split("---") if p.strip()]

        if len(parts) != 4:
            log.warning(f"Thread generation returned {len(parts)} parts instead of 4")
            return None

        # Quick length validation
        for i, part in enumerate(parts, 1):
            if len(part) > 280:
                log.warning(f"Thread part {i} too long ({len(part)} chars)")
                return None

        log.info("Thread generated successfully")
        return parts

    except anthropic.RateLimitError as e:
        log.warning(f"Rate limit hit during thread generation: {e}")
        time.sleep(30)
        return None
    except Exception as e:
        log.error(f"Thread generation failed: {type(e).__name__}: {e}")
        return None