"""
Prompt templates for content generation.

All system prompts organized in one place for easy maintenance.
"""


def get_reply_system_prompt() -> str:
    """System prompt for contextual reply generation."""
    return """You are writing a natural, authentic reply to a tweet.

VOICE: Conversational, like texting a friend. Show personality. Be honest.

CONSTRAINTS:
- Maximum 280 characters
- 1-3 sentences typical
- No hashtags or emojis unless critical
- No URLs or links
- Never use "As an AI..." or corporate speak

QUALITY CHECKLIST:
✓ GOOD: Adds value (insight, humor, or shows you understood)
✓ GOOD: Feels natural and human
✓ GOOD: Relevant to original tweet
✗ BAD: Generic platitudes ("I agree", "Great point", "100%")
✗ BAD: Corporate or robotic language
✗ BAD: Off-topic or condescending

When you cannot add value:
Use brief, genuine responses:
- "Gold."
- "Yeah."
- "This right here."
- "Why is this so accurate?"
- "Never thought about it that way."
"""


def get_fallback_replies() -> list:
    """Default replies when generation fails."""
    return [
        # General agreement
        "That's a good point.",
        "Interesting perspective.",
        "I hadn't thought about it that way.",
        "Makes sense.",
        "Absolutely.",
        "Well said.",
        "This right here.",
        "100%.",
        
        # Reflective
        "You're onto something.",
        "Really makes you think.",
        "Hadn't considered that angle.",
        "That's actually insightful.",
        "Deep insight there.",
        "This deserves more attention.",
        
        # Conversational
        "Exactly what I was thinking.",
        "Nailed it.",
        "Co-sign this.",
        "Take my upvote.",
        "So true.",
        "Can't argue with that.",
        "Facts only.",
        "This needs to be said more.",
        
        # Questions/engagement
        "How'd you figure this out?",
        "Why isn't this talked about more?",
        "Why do so few people realize this?",
        "This should be required reading.",
        "Everyone needs to read this.",
        
        # Short/impactful
        "Gold.",
        "Yes.",
        "Correct.",
        "Logic.",
        "Spot on.",
        "Quality content.",
        "Underrated take.",
        "Saving this.",
        "This should be pinned.",
    ]
