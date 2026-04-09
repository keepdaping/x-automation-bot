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

Scoring logic:
  Pass 1  — any single HIGH phrase          → score 3 immediately
  Pass 2  — struggle-marker accumulation   → 2+ markers OR (1 marker + "?") → score 2
  Pass 3  — any single MEDIUM phrase       → score 2
  Pass 4  — single "?" + MEDIUM phrase     → promoted to score 3
  Default — score 1
"""

from logger_setup import log

# ── HIGH-INTENT phrases ────────────────────────────────────────────────────
# One match = score 3 immediately.  Ordered from strongest to weakest signal.
HIGH_INTENT_PHRASES = [
    # Explicit client/lead pain
    "need clients", "need customers", "no clients",
    "can't get clients", "cant get clients",
    "can't find clients", "cant find clients",
    "looking for clients", "looking for customers",
    "how to get clients", "how do i get clients",
    "struggling to get clients", "struggle to get clients",
    "not getting clients", "getting no clients",
    # Sales / revenue pain
    "no sales", "zero sales", "not selling",
    "no one is buying", "nobody is buying",
    "can't make sales", "cant make sales",
    "no revenue", "need revenue", "need leads", "no leads",
    "how to monetize", "can't monetize", "cant monetize",
    "losing money", "wasting money",
    # Automation / tool pain
    "automation not working", "automation isn't working",
    "automation is broken", "my automation broke",
    "need help with automation", "help with automation",
    "automation failing", "automation failed",
    "workflow not working", "workflow broken",
    # Engagement / reach pain
    "no engagement", "zero engagement", "0 engagement",
    "no engagement on posts", "getting no engagement",
    "nobody sees", "no one sees", "no views", "no impressions",
    "getting zero impressions", "low reach", "no reach",
    "struggling to grow", "can't grow", "not growing",
    "dead account", "account dead",
    # Freelance / work pain
    "freelance is hard", "freelancing is hard",
    "no gigs", "can't find work", "need work",
    "underpaid", "low rates", "cheap clients",
    # Result frustration
    "nothing working", "nothing is working", "nothing works",
    "not getting results", "getting no results",
    "tried everything", "tried everything but",
    "no results at all", "zero results",
    # Help / desperation signals
    "i need help", "someone help", "please help",
    "what am i doing wrong", "what am i missing",
    "how do i get", "how do you get",
    "any tips on", "advice on growing",
    "desperate for", "really struggling",
    "business dying", "urgent", "emergency",
    # Earnings frustration
    "not making money", "making no money", "0 sales",
    "made nothing", "earned nothing",
]

# ── MEDIUM-INTENT phrases ──────────────────────────────────────────────────
# One match = score 2.  One match + a question mark = promoted to score 3.
MEDIUM_INTENT_PHRASES = [
    # Exploration / research signals
    "looking for", "looking for a tool", "looking for help",
    "any recommendations", "what tools", "which tool",
    "best way to", "how to start", "considering",
    "thinking about", "worth it?", "good idea?",
    # Early-stage building
    "just started", "starting out", "new to",
    "building my", "working on", "launching",
    "trying to", "learning to", "figuring out",
    "first client", "first sale", "first project",
    "side project", "side hustle",
    "building in public", "shipping",
    "growing my", "grow my account",
    # Soft help-seeking
    "help me", "can someone", "does anyone know",
    "how do i", "how do you", "is there a way",
    "anyone used", "has anyone tried",
    # Tool / service interest
    "automate my", "automating my",
    "need a tool", "need software", "need a way to",
]

# ── STRUGGLE MARKERS (accumulation scoring) ────────────────────────────────
# Partial frustration signals that individually score LOW but together signal MEDIUM.
# Rule: 2+ markers → score 2 | 1 marker + "?" → score 2
_STRUGGLE_MARKERS = [
    "struggling", "frustrated", "frustrating",
    "can't figure", "cant figure",
    "doesn't work", "not working", "isn't working",
    "giving up", "want to quit",
    "wasted time", "waste of time",
    "getting nowhere", "going nowhere",
    "so hard", "really hard", "so difficult",
    "confused about", "don't understand", "dont understand",
    "lost with", "stuck on", "stuck with",
    "any advice", "any suggestions", "any help",
    "help needed", "need advice",
]


def score_intent(tweet_text: str) -> int:
    """
    Score a tweet's intent level.

    Returns:
        3 = high intent (pain/need expressed)
        2 = medium intent (building/exploring/researching)
        1 = low intent (general discussion)
    """
    if not tweet_text:
        return 1

    text_lower = tweet_text.lower()
    has_question = "?" in text_lower

    # ── Pass 1: single HIGH phrase → immediate score 3 ────────────────────
    for phrase in HIGH_INTENT_PHRASES:
        if phrase in text_lower:
            log.debug(f"High intent detected: '{phrase}'")
            return 3

    # ── Pass 2: struggle-marker accumulation ──────────────────────────────
    # Two or more partial-frustration markers compound into a MEDIUM signal
    # without needing an explicit pain phrase.  One marker + "?" also qualifies.
    markers_found = [m for m in _STRUGGLE_MARKERS if m in text_lower]
    if len(markers_found) >= 2:
        log.debug(f"Medium intent: struggle accumulation {markers_found[:3]}")
        return 2
    if markers_found and has_question:
        log.debug(f"Medium intent: struggle marker + question ({markers_found[0]})")
        return 2

    # ── Pass 3: single MEDIUM phrase → score 2 ────────────────────────────
    for phrase in MEDIUM_INTENT_PHRASES:
        if phrase in text_lower:
            # ── Pass 3a: MEDIUM phrase + question → promote to HIGH ────────
            # A researching tweet with an explicit question signals active intent
            # to act, not passive browsing.
            if has_question:
                log.debug(f"High intent (promoted): MEDIUM phrase + '?' ({phrase})")
                return 3
            log.debug(f"Medium intent detected: '{phrase}'")
            return 2

    # ── Pass 4: multiple questions alone → MEDIUM ─────────────────────────
    if text_lower.count("?") >= 2:
        log.debug(f"Medium intent: multiple questions ({text_lower.count('?')})")
        return 2

    return 1


def get_intent_label(score: int) -> str:
    """Human-readable label for intent score."""
    return {3: "HIGH", 2: "MEDIUM", 1: "LOW"}.get(score, "LOW")