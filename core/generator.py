"""
AI content generation using Claude.
Updated to use current model names.
"""

import time
from anthropic import Anthropic, APIError, AuthenticationError
from config import Config
from logger_setup import log

_ai_client: Anthropic | None = None
_last_generation_metrics = {"model": None, "tokens": None, "duration": None, "success": False}


def get_last_generation_metrics() -> dict:
    return _last_generation_metrics.copy()


def _get_client() -> Anthropic:
    global _ai_client
    if _ai_client is None:
        if not Config.ANTHROPIC_API_KEY:
            log.critical("❌ ANTHROPIC_API_KEY not configured!")
            raise ValueError("ANTHROPIC_API_KEY is required")

        if Config.ANTHROPIC_API_KEY == "your_api_key_here":
            log.critical("❌ ANTHROPIC_API_KEY is placeholder!")
            raise ValueError("ANTHROPIC_API_KEY contains placeholder")

        try:
            _ai_client = Anthropic(api_key=Config.ANTHROPIC_API_KEY)
            log.debug("✓ Anthropic client initialized")
        except AuthenticationError as e:
            log.critical(f"❌ Auth failed: {e}")
            raise
    return _ai_client


def generate_contextual_reply(tweet_text: str, system_prompt: str = None, user_message: str = None) -> str:
    """Generate content via Claude. Used for both replies and original tweets.

    Args:
        tweet_text: The tweet to reply to, or a topic seed for original tweets.
        system_prompt: Custom system prompt.
        user_message: Custom user message. If None, defaults to reply format.
    """
    if system_prompt is None:
        system_prompt = _get_default_reply_system_prompt()

    if user_message is None:
        user_message = f'Reply to this tweet:\n\n"{tweet_text}"'

    client = _get_client()
    start_time = time.time()

    for model in Config.AI_MODELS_TO_TRY:
        try:
            response = client.messages.create(
                model=model,
                max_tokens=Config.AI_MAX_TOKENS,
                system=system_prompt,
                messages=[{"role": "user", "content": user_message}]
            )

            duration = time.time() - start_time
            tokens = None
            usage = getattr(response, "usage", None)
            if usage:
                tokens = getattr(usage, "output_tokens", None) or getattr(usage, "completion_tokens", None)

            _last_generation_metrics.update({"model": model, "tokens": tokens, "duration": duration, "success": True})

            reply = response.content[0].text.strip()
            log.debug(f"Generated reply using {model}")
            return reply

        except AuthenticationError as e:
            _last_generation_metrics.update({"model": model, "duration": time.time() - start_time, "success": False})
            log.critical(f"❌ API auth failed: {str(e)[:100]}")
            raise
        except APIError as e:
            _last_generation_metrics.update({"model": model, "duration": time.time() - start_time, "success": False})
            error_msg = str(e)
            if "429" in error_msg or "rate" in error_msg.lower():
                log.warning(f"Rate limited on {model}, stopping: {error_msg[:50]}")
                break
            else:
                log.debug(f"Model {model} error: {error_msg[:50]}")
                continue
        except Exception as e:
            _last_generation_metrics.update({"model": model, "duration": time.time() - start_time, "success": False})
            log.debug(f"Model {model} failed: {str(e)[:50]}")
            continue

    _last_generation_metrics.update({"duration": time.time() - start_time, "success": False})
    log.warning("All models failed to generate reply")
    return ""


def _get_default_reply_system_prompt() -> str:
    return """You are a tweet reply ghostwriter. Output ONLY the reply text — nothing else.

CRITICAL: No labels, no explanations. Just the reply.

LANGUAGE:
- Use very simple words (grade 5-8 level)
- Short words > long words
- A 15-year-old should understand it instantly
- Simple > smart. Clear > clever.

STYLE:
- Under 20 words
- Like texting a friend
- Easy for them to respond to in 5 seconds

PREFER:
- Simple observations
- Relatable one-liners
- Short casual questions

AVOID:
- Long or structured questions
- Big or fancy words
- Smart-sounding tone
- Generic ("I agree", "Great point")
- Anything over 30 words

NEVER USE: leverage, optimize, utilize, facilitate, essentially, fundamentally, nuanced, paradigm
"""
