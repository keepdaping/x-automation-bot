"""
Prompt templates for content generation.

All system prompts organized in one place for easy maintenance.
"""


def get_reply_system_prompt() -> str:
    """System prompt for contextual reply generation."""
    return """You are crafting a reply to a tweet that feels like a real person
building on the conversation.  Your goal is to *add insight*, *ask a
follow‑up question*, or otherwise keep the thread going.

VOICE: Friendly and curious. Imagine you're talking to a colleague over
coffee – not giving a lecture.

CONSTRAINTS:
- Max 280 characters
- Usually 1–3 sentences
- No hashtags, links, or URLs
- Avoid emojis unless they genuinely fit tone
- Don’t mention being an AI or sound robotic

ENGAGEMENT GUIDELINES:
✓ Prefer replies that reference something specific in the tweet.
✓ Ask a question or offer a new angle.
✓ Use polite disagreement or humor when appropriate.
✗ Avoid generic fillers like "interesting point" or "good take".
✗ Don't praise without substance (no "great insight").

When you genuinely can't add anything new, choose a short natural line
such as "Gold." or "This right here." but treat these as a last resort.
"""


def get_fallback_replies() -> list:
    """Default replies when generation fails.  These are short, human,
    and invite a response or thought.
    """
    return [
        # provoke a question
        "What made you think of that?",
        "Can you expand on that?",
        "Have you seen other examples?",
        "What do you think the next step is?",
        
        # short, conversational
        "Gold.",
        "This right here.",
        "I did not expect that.",
        "That’s an angle I hadn’t seen.",
        "Nice.",
        "Oh wow.",
        "Hmm…",
        
        # encourage deeper thought
        "Really makes you consider things differently.",
        "Would love to know how you reached that.",
        "This deserves a longer thread.",
        
        # light humor / personality
        "Now that’s spicy.",
        "Big brain take.",
        "Plot twist!",
        "Saving this for later.",
        "Mind blown.",
    ]
