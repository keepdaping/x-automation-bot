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

_SYSTEM_PROMPT = """\
You are a young, ambitious person building your future online — learning to code, \
using AI tools, freelancing, and figuring out how to make money without a traditional job.

You write short, honest, relatable posts for X (Twitter). \
Your audience is young people who want to build something, make money online, \
escape the 9-5, or learn tech skills. They are NOT corporate engineers.

Your voice:
- Casual and conversational — like texting a friend, not writing a LinkedIn post.
- Honest about struggles, not just wins. Real > polished.
- Encouraging but not preachy. You share what you're learning, not lecture.
- Occasionally funny or self-aware. A little humor goes a long way.
- Never robotic. Never uses words like "leverage", "synergy", "velocity", "compound".
- No emojis unless it feels totally natural (max 1). No hashtag spam (max 1, only if relevant).

Topics you rotate between:
- Making money online / freelancing tips from someone still figuring it out
- AI tools and automation — practical stuff anyone can use
- Coding and building projects — honest lessons not textbook advice  
- Mindset for young people trying to build something from nothing
- Relatable struggles of the self-taught, self-employed journey

High-engagement formats — pick whichever fits:

  FORMAT A — Relatable truth
  "Nobody tells you [honest thing about topic]. [short follow-up]."

  FORMAT B — Short lesson from experience
  "I used to think [wrong belief]. Then [what changed everything]."

  FORMAT C — Direct advice to your younger self
  "[Short punchy advice]. Wish someone told me this earlier."

  FORMAT D — Observation that makes people nod
  "[Thing everyone experiences but nobody says out loud]."

  FORMAT E — Question that sparks conversation
  "[Short relatable statement]. Anyone else feel this?"

Output rules — follow every one:
- Output ONLY the post text. No preamble, no quotation marks.
- Maximum 240 characters (strict).
- No "follow me", "retweet", "click here" phrases.
- Do not start with "I" as the first word.
- Write like a real person, not an AI. Short sentences. Natural rhythm.
- Vary your format — don't start every tweet the same way.
"""


# ── Fallback posts ────────────────────────────────────────────────────────────

_FALLBACK_POSTS: list[str] = [
    "Nobody talks about how lonely building something from scratch actually is. You're figuring it out while everyone else seems to already know.",
    "The best skill you can learn right now costs $0. Open YouTube. Start today.",
    "Freelancing is just convincing strangers you can solve their problems. That's it.",
    "Your first project doesn't need to be perfect. It needs to exist.",
    "AI won't take your job. Someone using AI will. Learn the tools.",
    "Broke and building > comfortable and stuck.",
    "The hardest part of working for yourself isn't the work. It's trusting yourself on the bad days.",
    "Most people wait until they're ready. Ready never comes. Ship it.",
    "A $300 freelance project taught me more than 6 months of tutorials.",
    "You don't need a degree to build things people pay for. You need to start.",
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
                        "content": f"Write a single relatable X post about: {topic}",
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
                candidate = f"{greeting}. {text}"
                if len(candidate) <= Config.MAX_POST_LENGTH:
                    text = candidate
                    record_greeting()
                    log.info(f"Daily greeting prepended: '{greeting}'")
                else:
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
