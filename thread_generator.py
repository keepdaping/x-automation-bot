# thread_generator.py
"""
Generates multi-tweet threads (4 tweets) for higher reach and follower growth.
Threads get 3-5x more algorithmic distribution than single tweets on X.
"""
from __future__ import annotations

import json
import time
import random
import anthropic

from config import Config
from logger_setup import log


_ai_client: anthropic.Anthropic | None = None


def _get_ai_client() -> anthropic.Anthropic:
    global _ai_client
    if _ai_client is None:
        _ai_client = anthropic.Anthropic(api_key=Config.ANTHROPIC_API_KEY)
    return _ai_client


_THREAD_SYSTEM_PROMPT = """\
You are a young person building in public — learning to code, freelancing, \
and sharing your journey online. You write Twitter/X threads that grow followings fast.

Your voice:
- Casual, honest, relatable — like texting a friend who's on the same journey.
- Short punchy sentences. Real experiences, not generic advice.
- Encouraging without being preachy or fake.

Write a thread of exactly 4 tweets on the given topic.

Thread structure:
  Tweet 1 — HOOK: One bold, curious, or surprising statement that stops scrolling.
             Must make the reader want to read more. End with "🧵"
  Tweet 2 — THE PROBLEM or STORY: Expand on the hook. Make it relatable.
  Tweet 3 — THE INSIGHT or LESSON: The real value. What you learned or figured out.
  Tweet 4 — THE CLOSE: Something memorable. A challenge, truth, or question
             that makes people want to reply or share.

Rules:
- Each tweet maximum 240 characters. Count carefully.
- No corporate speak. No "leverage", "synergy", "optimize", "compound".
- Max 1 hashtag in the ENTIRE thread, only in tweet 4 if relevant.
- No "follow me for more" or engagement-beg phrases.
- The thread must flow naturally from tweet 1 to tweet 4.

Output FORMAT — return ONLY a valid JSON array, nothing else:
["Tweet 1 text", "Tweet 2 text", "Tweet 3 text", "Tweet 4 text"]

No preamble. No explanation. Just the JSON array.
"""


_FALLBACK_THREADS: list[list[str]] = [
    [
        "The internet changed everything. But most people are still playing by old rules. 🧵",
        "A year ago I had no clients, no portfolio, nothing. Just a laptop and YouTube tutorials. I felt behind everyone.",
        "Then I stopped waiting to be 'ready' and just started building things and sharing the process. That one decision changed everything.",
        "People don't hire perfect. They hire someone they've watched grow. Start showing your work today — even when it's messy.",
    ],
    [
        "You don't need a degree to make money online in 2025. Here's what actually matters. 🧵",
        "Most people spend months in tutorial hell — watching courses, taking notes, never building anything real. That was me too.",
        "The shift happened when I built one real project and put it online. That got me more opportunities than 6 months of studying.",
        "Skills + proof of work + consistency online. That's the whole formula. No degree required.",
    ],
    [
        "AI won't take your job. Someone using AI better than you will. Here's how to stay ahead. 🧵",
        "Most people treat AI like a search engine — ask a question, get an answer. That's using 10% of what it can do.",
        "The people winning right now use AI to automate repetitive work, generate ideas faster, and deliver better results to clients.",
        "Start with one thing: automate something you do every day. That's how you go from AI user to AI builder.",
    ],
]


def get_fallback_thread() -> list[str]:
    thread = random.choice(_FALLBACK_THREADS)
    log.warning("Using fallback thread.")
    return thread


def _parse_thread(raw: str) -> list[str] | None:
    try:
        raw = raw.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        tweets = json.loads(raw.strip())
        if isinstance(tweets, list) and len(tweets) >= 3:
            tweets = [t[:240] for t in tweets if isinstance(t, str) and t.strip()]
            return tweets
    except Exception as exc:
        log.error(f"[Thread] Failed to parse thread JSON: {exc}")
    return None


def generate_thread(topic: str) -> tuple[list[str], str]:
    """
    Generate a 4-tweet thread on the given topic.
    Returns: (tweets_list, source) where source is 'ai' or 'fallback'
    """
    client = _get_ai_client()

    for attempt in range(1, Config.AI_MAX_RETRIES + 1):
        try:
            log.info(
                f"[Thread] Generating thread (attempt {attempt}/{Config.AI_MAX_RETRIES}) "
                f"— topic: '{topic}'"
            )

            message = client.messages.create(
                model=Config.AI_MODEL,
                max_tokens=600,
                system=_THREAD_SYSTEM_PROMPT,
                messages=[
                    {
                        "role": "user",
                        "content": f"Write a 4-tweet thread about: {topic}",
                    }
                ],
            )

            raw = message.content[0].text
            tweets = _parse_thread(raw)

            if tweets:
                log.info(f"[Thread] Generated {len(tweets)}-tweet thread successfully.")
                return tweets, "ai"

            log.warning(f"[Thread] Attempt {attempt} — could not parse thread response.")

        except anthropic.RateLimitError:
            wait = 2 ** attempt
            log.warning(f"[Thread] Rate limit — waiting {wait}s…")
            time.sleep(wait)

        except anthropic.APIStatusError as exc:
            log.error(f"[Thread] API error {exc.status_code}: {exc.message}")
            if exc.status_code < 500:
                break
            time.sleep(2 ** attempt)

        except (anthropic.APIConnectionError, anthropic.APITimeoutError) as exc:
            wait = 2 ** attempt
            log.warning(f"[Thread] Connection error: {exc} — waiting {wait}s…")
            time.sleep(wait)

        except KeyboardInterrupt:
            raise

        except Exception as exc:
            log.error(f"[Thread] Unexpected error: {type(exc).__name__}: {exc}")
            break

    log.warning("[Thread] All AI attempts failed — using fallback thread.")
    return get_fallback_thread(), "fallback"
