"""
AI content generation using Claude.

Minimal, focused module for LLM calls only.
Orchestration and validation happens in content/ module.
"""

import time

from anthropic import Anthropic, APIError, AuthenticationError
from config import Config
from logger_setup import log

_ai_client: Anthropic | None = None
_last_generation_metrics = {
    "model": None,
    "tokens": None,
    "duration": None,
    "success": False,
}


def get_last_generation_metrics() -> dict:
    """Return metrics for the last LLM generation."""
    return _last_generation_metrics.copy()


def _get_client() -> Anthropic:
    """Get or create singleton Anthropic client."""
    global _ai_client
    if _ai_client is None:
        # Verify API key is set before creating client
        if not Config.ANTHROPIC_API_KEY:
            log.critical("❌ ANTHROPIC_API_KEY not configured!")
            log.critical(f"   Status: {Config._api_key_source}")
            raise ValueError("ANTHROPIC_API_KEY is required")
        
        if Config.ANTHROPIC_API_KEY == "your_api_key_here":
            log.critical("❌ ANTHROPIC_API_KEY is set to placeholder value!")
            log.critical("   Replace in .env: ANTHROPIC_API_KEY=sk-ant-your-actual-key")
            raise ValueError("ANTHROPIC_API_KEY contains placeholder, not real key")
        
        try:
            _ai_client = Anthropic(api_key=Config.ANTHROPIC_API_KEY)
            log.debug("✓ Anthropic client initialized successfully")
        except AuthenticationError as e:
            log.critical(f"❌ Anthropic API authentication failed: {e}")
            log.critical(f"   Check that your ANTHROPIC_API_KEY is valid")
            log.critical(f"   Get it from: https://console.anthropic.com/account/keys")
            raise
        except APIError as e:
            log.critical(f"❌ Anthropic API error: {e}")
            raise
    
    return _ai_client


def generate_contextual_reply(tweet_text: str, system_prompt: str = None) -> str:
    """Generate a contextual reply to a tweet using Claude.

    Args:
        tweet_text: The original tweet content
        system_prompt: Optional custom system prompt

    Returns:
        Generated reply text (empty string if all models fail)
    """

    if system_prompt is None:
        system_prompt = _get_default_reply_system_prompt()

    client = _get_client()
    start_time = time.time()

    # Try each model in sequence
    for model in Config.AI_MODELS_TO_TRY:
        try:
            response = client.messages.create(
                model=model,
                max_tokens=100,
                system=system_prompt,
                messages=[
                    {
                        "role": "user",
                        "content": f'Reply to this tweet:\n\n"{tweet_text}"'
                    }
                ]
            )

            duration = time.time() - start_time
            tokens = None
            usage = getattr(response, "usage", None)
            if isinstance(usage, dict):
                tokens = usage.get("total_tokens") or usage.get("completion_tokens")
            elif hasattr(response, "completion_tokens"):
                tokens = getattr(response, "completion_tokens")

            _last_generation_metrics.update(
                {
                    "model": model,
                    "tokens": tokens,
                    "duration": duration,
                    "success": True,
                }
            )

            reply = response.content[0].text.strip()
            log.debug(f"Generated reply using {model}")
            return reply

        except AuthenticationError as e:
            # Fatal: API key is invalid
            duration = time.time() - start_time
            _last_generation_metrics.update(
                {"model": model, "duration": duration, "success": False}
            )
            log.critical(f"❌ API authentication failed: {str(e)[:100]}")
            log.critical(f"   Check ANTHROPIC_API_KEY is correct")
            # Don't retry other models, auth error is fatal
            raise
        except APIError as e:
            duration = time.time() - start_time
            _last_generation_metrics.update(
                {"model": model, "duration": duration, "success": False}
            )
            # Temporary error or rate limit
            error_msg = str(e)
            if "429" in error_msg or "rate" in error_msg.lower():
                log.warning(f"Rate limited on {model}, stopping retry: {error_msg[:50]}")
                break  # Don't retry if rate limited
            else:
                log.debug(f"Model {model} error: {error_msg[:50]}")
                continue  # Try next model
        except Exception as e:
            duration = time.time() - start_time
            _last_generation_metrics.update(
                {"model": model, "duration": duration, "success": False}
            )
            log.debug(f"Model {model} failed: {str(e)[:50]}")
            continue

    # All models failed
    duration = time.time() - start_time
    _last_generation_metrics.update({"duration": duration, "success": False})
    log.warning("All models failed to generate reply")
    return ""


def _get_default_reply_system_prompt() -> str:
    """Default system prompt for reply generation."""
    return """You are writing a natural, authentic reply to a tweet.

VOICE: Conversational, like texting a friend. Show personality. Be honest.

CONSTRAINTS:
- Maximum 280 characters
- 1-3 sentences typical
- No hashtags or emojis unless perfect fit
- No URLs
- Never sound like AI

QUALITY SIGNALS:
✓ GOOD: Adds value (insight, humor, shows you understood)
✓ GOOD: Feels natural and human
✓ GOOD: Relevant to the tweet
✗ BAD: Generic ("I agree", "Great point")
✗ BAD: Corporate speak or robotic
✗ BAD: Off-topic or condescending

When can't add value:
- "Gold."
- "Yeah."
- "This right here."
- "Why is this so accurate?"
"""
