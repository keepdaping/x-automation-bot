"""
Multi-turn conversation graph (Phase 2) – simple if/else state machine.
"""

from content.engine import get_content_engine
from content.conversation_memory import ConversationMemory
from config import Config
from logger_setup import log

def generate_next_reply(tweet_text: str, user_handle: str, history: list) -> str:
    """Returns natural next reply using memory."""
    if not Config.CONVERSATION_ENABLED:
        # fallback to old single-reply
        return get_content_engine().generate_curiosity_reply(tweet_text).text

    memory = ConversationMemory()
    hist = memory.get_relevant_history(user_handle)
    memory.close()

    prompt_context = f"Previous turns: {hist}\nCurrent tweet: {tweet_text}"
    # Reuse your existing engine with extra context
    result = get_content_engine().generate_curiosity_reply(tweet_text)  # you can extend engine later
    return result.text