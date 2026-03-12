"""
AI content generation using Claude.

Minimal, focused module for LLM calls only.
Orchestration and validation happens in content/ module.
"""

from anthropic import Anthropic
from config import Config
from logger_setup import log

_ai_client: Anthropic | None = None


def _get_client() -> Anthropic:
    """Get or create singleton Anthropic client."""
    global _ai_client
    if _ai_client is None:
        _ai_client = Anthropic(api_key=Config.ANTHROPIC_API_KEY)
    return _ai_client


def generate_contextual_reply(tweet_text: str, system_prompt: str = None) -> str:
    """
    Generate a contextual reply to a tweet using Claude.
    
    Args:
        tweet_text: The original tweet content
        system_prompt: Optional custom system prompt
    
    Returns:
        Generated reply text (empty string if all models fail)
    """
    
    if system_prompt is None:
        system_prompt = _get_default_reply_system_prompt()
    
    client = _get_client()
    
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
            
            reply = response.content[0].text.strip()
            log.debug(f"Generated reply using {model}")
            return reply
        
        except Exception as e:
            log.debug(f"Model {model} failed: {str(e)[:50]}")
            continue
    
    # All models failed
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
