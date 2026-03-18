"""
Intent scoring system - detects pain signals in tweets.

Scores tweets 1-3 based on how likely the person is a potential lead:
  3 = High intent (expressing pain, need, frustration)
  2 = Medium intent (exploring, learning, building)
  1 = Low intent (general discussion, sharing, opinions)

The bot uses this to decide HOW to engage:
  High (3)  → reply with curiosity-driven prompt (100%)
  Medium (2) → reply with standard prompt (30% chance)
  Low (1)   → like only
"""

import re
from logger_setup import log


# High-intent phrases — person is expressing a NEED or PAIN
HIGH_INTENT_PHRASES = [
    # Growth frustration
    "no engagement", "zero engagement", "0 engagement",
    "nobody sees", "no one sees", "no views", "no impressions",
    "struggling to grow", "can't grow", "not growing",
    "low reach", "no reach", "dead account",
    # Client/money pain
    "need clients", "need customers", "no clients",
    "no sales", "zero sales", "not selling",
    "need leads", "no leads", "need revenue",
    "how to monetize", "can't monetize",
    "no one is buying", "nobody is buying",
    # Freelance frustration
    "freelance is hard", "freelancing is hard",
    "no gigs", "can't find work", "need work",
    "underpaid", "low rates", "cheap clients",
    # Help seeking
    "how do i get", "how do you get",
    "what am i doing wrong", "what am i missing",
    "any tips on", "advice on growing",
    "i need help", "someone help",
]

# Medium-intent phrases — person is actively building/learning
MEDIUM_INTENT_PHRASES = [
    "just started", "starting out", "new to",
    "building my", "working on", "launching",
    "trying to", "learning to", "figuring out",
    "first client", "first sale", "first project",
    "any recommendations", "what tools",
    "side project", "side hustle",
    "building in public", "shipping",
    "growing my", "grow my account",
]


def score_intent(tweet_text: str) -> int:
    """
    Score a tweet's intent level.

    Args:
        tweet_text: The tweet text to analyze

    Returns:
        3 = high intent (pain/need)
        2 = medium intent (building/learning)
        1 = low intent (general)
    """
    if not tweet_text:
        return 1

    text_lower = tweet_text.lower()

    # Check high-intent phrases first
    for phrase in HIGH_INTENT_PHRASES:
        if phrase in text_lower:
            log.debug(f"High intent detected: '{phrase}'")
            return 3

    # Check medium-intent phrases
    for phrase in MEDIUM_INTENT_PHRASES:
        if phrase in text_lower:
            log.debug(f"Medium intent detected: '{phrase}'")
            return 2

    # Question marks suggest seeking help (slight bump)
    if text_lower.count("?") >= 2:
        return 2

    return 1


def get_intent_label(score: int) -> str:
    """Human-readable label for intent score."""
    return {3: "HIGH", 2: "MEDIUM", 1: "LOW"}.get(score, "LOW")
