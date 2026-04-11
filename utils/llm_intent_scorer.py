"""
LLM-powered intent scorer (Phase 1 of 2026 redesign).
Uses Claude Haiku for fast, accurate scoring with negation/context awareness.
Fully backward compatible – can run alongside old keyword scorer.
"""

import json
from anthropic import Anthropic
from config import Config
from logger_setup import log

class LLMIntentScorer:
    def __init__(self):
        self.client = Anthropic(api_key=Config.ANTHROPIC_API_KEY)
        self.model = "claude-haiku-4-5-20251001"  # cheapest & fast

    def score(self, tweet_text: str, bio: str = "", recent_tweets: list = None) -> dict:
        """
        Returns structured score:
        {
            "intent_score": 1-3,
            "level": "HIGH|MEDIUM|LOW",
            "pain_points": [...],
            "reason": "...",
            "negation_check": bool
        }
        """
        if not tweet_text:
            return {"intent_score": 1, "level": "LOW", "pain_points": [], "reason": "empty", "negation_check": False}

        context = f"Bio: {bio}\nRecent: {' | '.join(recent_tweets[:3]) if recent_tweets else ''}"

        prompt = f"""You are an expert lead-gen intent detector for X/Twitter.
Tweet: "{tweet_text}"
{context}

Score intent 1-3:
- 3 = HIGH (pain, need clients, struggling to grow, zero sales, etc.)
- 2 = MEDIUM (building, asking how-to, exploring)
- 1 = LOW (general chat, opinions)

Output ONLY valid JSON:
{{
  "intent_score": 1|2|3,
  "level": "HIGH|MEDIUM|LOW",
  "pain_points": ["growth", "sales", ...],
  "reason": "one short sentence",
  "negation_check": true/false
}}"""

        resp = self.client.messages.create(
            model=self.model,
            max_tokens=300,
            temperature=0,
            messages=[{"role": "user", "content": prompt}]
        )
        result = json.loads(resp.content[0].text.strip())
        log.debug(f"LLM intent: {result['level']} | {result['reason']}")
        return result

# Singleton
_llm_scorer = None
def get_llm_intent_scorer():
    global _llm_scorer
    if _llm_scorer is None:
        _llm_scorer = LLMIntentScorer()
    return _llm_scorer