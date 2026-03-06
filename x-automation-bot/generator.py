# generator.py
from __future__ import annotations

import random
import time
from datetime import datetime
import anthropic

from config import Config
from database import has_greeted_today, record_greeting
from logger_setup import log


# ── Anthropic client (lazy) ───────────────────────────────────────────────────

_ai_client: anthropic.Anthropic | None = None


def _get_ai_client() -> anthropic.Anthropic:
    global _ai_client
    if _ai_client is None:
        _ai_client = anthropic.Anthropic(api_key=Config.ANTHROPIC_API_KEY)
    return _ai_client


# ── System prompt ─────────────────────────────────────────────────────────────
# Improved with concrete high-engagement format guidance used by
# top tech accounts (contrarian insight, numbered lesson, system thinking, etc.)

_SYSTEM_PROMPT = """\
You are a sharp, opinionated software engineer with 10+ years of backend experience.
You write short, punchy posts for X (Twitter) aimed at developers and technical builders.

Your voice:
- Direct, confident, occasionally contrarian — grounded in real experience.
- No corporate speak. No emojis. No hashtag spam (use at most one, only when genuinely relevant).
- Short sentences. One idea per post. End with a hook, open question, or a twist.

Audience: backend engineers, API builders, engineering managers, technical founders.

High-engagement formats — pick whichever fits the topic best:

  FORMAT A — Contrarian insight
  "Everyone says X. The engineers who scale past Y know it's actually Z."

  FORMAT B — Numbered short lesson (max 3 items)
  "3 things that separate senior from junior engineers:\n1. ...\n2. ...\n3. ..."

  FORMAT C — Painful truth opener
  "Nobody tells you this about [topic]: [uncomfortable truth]."

  FORMAT D — System thinking
  "Your [system/team/codebase] doesn't have a [X] problem. It has a [root cause] problem."

  FORMAT E — Short insight + question
  "[Sharp observation in 1–2 sentences]. What's your experience?"

Output rules — follow every one:
- Output ONLY the post text. No preamble, no "here is your tweet:", no quotation marks.
- Maximum 240 characters (strict — count carefully).
- No "follow me", "retweet", "click here", or engagement-beg phrases.
- Do not start with "I" as the first word.
- Do not use filler openers like "Just", "Hot take:", "Unpopular opinion:".
"""


# ── Fallback posts — on-topic and niche-consistent ────────────────────────────

_FALLBACK_POSTS: list[str] = [
    "SELECT * is not a query. It's a tax you pay at 10× traffic.",
    "Idempotency and retry-safety are not the same thing. Most APIs conflate them.",
    "async def doesn't make your code faster. It makes it concurrent. Not the same.",
    "The HTTP status code your team misuses most: 200 with an error body.",
    "If you're versioning your API with /v1/ in the path, you've already lost.",
    "A database index that isn't covering is often slower than no index at all.",
    "You don't have a performance problem. You have a measurement problem.",
    "The best code review catches design issues, not style issues. Linters handle style.",
    "Most outages aren't caused by the change. They're caused by the rollback.",
    "You will read this code in 6 months and have no idea what you meant. Comment it.",
]


def get_fallback_post() -> str:
    post = random.choice(_FALLBACK_POSTS)
    log.warning(f"Using fallback post: '{post[:60]}…'")
    return post


# ── Output sanitisation ───────────────────────────────────────────────────────

_PREAMBLE_PREFIXES = (
    "here is a tweet:",
    "here's a tweet:",
    "here is your tweet:",
    "tweet:",
    "post:",
    "here you go:",
    "sure,",
    "sure!",
)


def _clean(text: str) -> str:
    text = text.strip().strip('"').strip("'").strip()
    lower = text.lower()
    for prefix in _PREAMBLE_PREFIXES:
        if lower.startswith(prefix):
            text = text[len(prefix):].strip()
            break
    return text


# ── Greeting ──────────────────────────────────────────────────────────────────

def _get_greeting() -> str | None:
    """
    Return a time-appropriate greeting string if:
      - Config.ENABLE_DAILY_GREETING is True
      - No greeting has been logged today in the DB

    Returns None if either condition is not met.
    """
    if not Config.ENABLE_DAILY_GREETING:
        return None
    if has_greeted_today():
        return None

    hour = datetime.now().hour
    if hour < 12:
        phrase = "Good morning"
    elif hour < 17:
        phrase = "Good afternoon"
    else:
        phrase = "Good evening"

    return phrase


# ── Topic picker ──────────────────────────────────────────────────────────────

def pick_topic() -> str:
    """Return a random topic from today's theme pool."""
    return random.choice(Config.get_todays_topics())


# ── Generation ────────────────────────────────────────────────────────────────

def generate_post(topic: str) -> tuple[str, str]:
    """
    Generate a tweet for `topic` using the Anthropic API.

    If Config.ENABLE_DAILY_GREETING is True and no greeting has been sent
    today, prepends a short time-appropriate greeting to the first post.

    Returns:
        (post_text, source)  where source is 'ai' or 'fallback'
    """
    client = _get_ai_client()

    for attempt in range(1, Config.AI_MAX_RETRIES + 1):
        try:
            log.info(
                f"Generating AI post (attempt {attempt}/{Config.AI_MAX_RETRIES}) "
                f"— topic: '{topic}'"
            )

            message = client.messages.create(
                model=Config.AI_MODEL,
                max_tokens=Config.AI_MAX_TOKENS,
                system=_SYSTEM_PROMPT,
                messages=[
                    {
                        "role": "user",
                        "content": f"Write a single X post about: {topic}",
                    }
                ],
            )

            raw_text = message.content[0].text
            text = _clean(raw_text)

            if not text:
                raise ValueError("AI returned an empty response after cleaning.")

            # ── Greeting injection ────────────────────────────────────────
            greeting = _get_greeting()
            if greeting:
                # Only prepend if the combined text stays within X's limit.
                candidate = f"{greeting}. {text}"
                if len(candidate) <= Config.MAX_POST_LENGTH:
                    text = candidate
                    record_greeting()
                    log.info(f"Daily greeting prepended: '{greeting}'")
                else:
                    # Post is too long to add a greeting — skip greeting this time.
                    log.debug("Greeting skipped — combined text would exceed character limit.")

            log.info(f"AI post generated — {len(text)} chars")
            return text, "ai"

        except anthropic.RateLimitError:
            wait = 2 ** attempt
            log.warning(f"Anthropic rate limit — waiting {wait}s before retry…")
            time.sleep(wait)

        except anthropic.APIStatusError as exc:
            log.error(f"Anthropic API error {exc.status_code}: {exc.message}")
            if exc.status_code < 500:
                break
            wait = 2 ** attempt
            time.sleep(wait)

        except (anthropic.APIConnectionError, anthropic.APITimeoutError) as exc:
            wait = 2 ** attempt
            log.warning(f"Connection/timeout error: {exc} — waiting {wait}s…")
            time.sleep(wait)

        except KeyboardInterrupt:
            raise

        except Exception as exc:
            log.error(f"Unexpected generation error: {type(exc).__name__}: {exc}")
            break

    log.warning(f"All {Config.AI_MAX_RETRIES} AI attempts failed — switching to fallback.")
    return get_fallback_post(), "fallback"
