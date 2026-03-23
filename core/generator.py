"""
AI content generation using Claude.
Updated to use current model names and stronger error handling.
"""

import time
from anthropic import Anthropic, APIError, AuthenticationError, RateLimitError
from config import Config
from logger_setup import log

# Global client and last metrics
_ai_client: Anthropic | None = None
_last_generation_metrics = {
    "model": None,
    "tokens": None,
    "duration": None,
    "success": False,
    "error": None,
}


def get_last_generation_metrics() -> dict:
    """Return a copy of the last generation metrics."""
    return _last_generation_metrics.copy()


def _get_client() -> Anthropic:
    """Lazy-initialize and return the Anthropic client."""
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
            log.critical(f"❌ Auth failed: {str(e)[:200]}")
            raise
        except Exception as e:
            log.critical(f"❌ Client initialization failed: {str(e)[:200]}")
            raise
    return _ai_client


def generate_contextual_reply(
    tweet_text: str,
    system_prompt: str = None,
    user_message: str = None,
    max_tokens: int = None,
    model: str = None,
) -> str:
    """
    Generate content via Claude. Used for replies, daily tweets, quotes, etc.

    Args:
        tweet_text: The tweet to reply to, or a topic seed for original tweets.
        system_prompt: Custom system prompt (defaults to basic reply prompt).
        user_message: Custom user message (defaults to reply format).
        max_tokens: Optional override for max tokens.
        model: Optional model override (defaults to Config.AI_MODEL).

    Returns:
        Generated text (stripped) or empty string on failure.
    """
    if system_prompt is None:
        system_prompt = """You are a tweet reply ghostwriter. Output ONLY the reply — nothing else.

CORE RULE: Write like you're texting a friend.

STYLE:
- Under 15 words
- Casual, slightly imperfect, natural
- Simple English (grade 5-8)
- It's okay to be a bit messy

PREFER:
- Direct statements
- Quick reactions
- Relatable phrases
- Light curiosity

AVOID:
- "I feel like...", "It seems...", "In my opinion..."
- Over-explaining or long sentences
- Formal or smart-sounding tone
- Generic ("I agree", "Great point")
- Anything over 20 words

EMOJI: only ~20-30% of replies, max 1, only 😂 😭 🤔 😅 😳

GOAL: Sound like a real person. NOT like AI."""

    if user_message is None:
        user_message = f'Reply to this tweet:\n\n"{tweet_text}"'

    client = _get_client()
    start_time = time.time()

    # Default to configured model, or allow override
    model_to_use = model or Config.AI_MODEL
    tokens_to_use = max_tokens or Config.AI_MAX_TOKENS

    try:
        response = client.messages.create(
            model=model_to_use,
            max_tokens=tokens_to_use,
            system=system_prompt,
            messages=[{"role": "user", "content": user_message}],
            temperature=0.7,  # Slightly creative but controlled
        )

        duration = time.time() - start_time
        tokens_used = None
        if hasattr(response, "usage"):
            tokens_used = getattr(response.usage, "output_tokens", None) or getattr(response.usage, "completion_tokens", None)

        _last_generation_metrics.update({
            "model": model_to_use,
            "tokens": tokens_used,
            "duration": duration,
            "success": True,
            "error": None,
        })

        reply = response.content[0].text.strip()
        log.debug(f"Generated reply using {model_to_use} ({tokens_used or '?'} tokens, {duration:.2f}s)")
        return reply

    except RateLimitError as e:
        _last_generation_metrics.update({
            "model": model_to_use,
            "duration": time.time() - start_time,
            "success": False,
            "error": f"Rate limit: {str(e)[:150]}",
        })
        log.warning(f"Claude rate limit hit: {str(e)[:100]}")
        return ""

    except AuthenticationError as e:
        _last_generation_metrics.update({
            "model": model_to_use,
            "duration": time.time() - start_time,
            "success": False,
            "error": f"Auth error: {str(e)[:150]}",
        })
        log.critical(f"❌ Claude auth failed: {str(e)[:150]}")
        raise

    except APIError as e:
        _last_generation_metrics.update({
            "model": model_to_use,
            "duration": time.time() - start_time,
            "success": False,
            "error": f"API error: {str(e)[:150]}",
        })
        log.error(f"Claude API error: {str(e)[:150]}")
        return ""

    except Exception as e:
        _last_generation_metrics.update({
            "model": model_to_use,
            "duration": time.time() - start_time,
            "success": False,
            "error": f"Unexpected error: {str(e)[:150]}",
        })
        log.error(f"Unexpected Claude error: {str(e)[:150]}", exc_info=True)
        return ""


def _get_default_reply_system_prompt() -> str:
    """Default system prompt for replies when none is provided."""
    return """You are a tweet reply ghostwriter. Output ONLY the reply — nothing else.

CORE RULE: Write like you're texting a friend.

STYLE:
- Under 15 words
- Casual, slightly imperfect, natural
- Simple English (grade 5-8)
- It's okay to be a bit messy

PREFER:
- Direct statements
- Quick reactions
- Relatable phrases
- Light curiosity

AVOID:
- "I feel like...", "It seems...", "In my opinion..."
- Over-explaining or long sentences
- Formal or smart-sounding tone
- Generic ("I agree", "Great point")
- Anything over 20 words

EMOJI: only ~20-30% of replies, max 1, only 😂 😭 🤔 😅 😳

GOAL: Sound like a real person. NOT like AI."""