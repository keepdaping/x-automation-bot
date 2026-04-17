"""
AgentController — ReAct (Reason + Act) autonomous cycle for X Automation Bot.

Replaces the static for-loop in run_engagement() with an agent that:
  THOUGHT  → reasons about current state and logs it to console
  STRATEGY → consults PolicyEngine + Bandit rewards before acting
  ACTION   → calls a named tool (search / analyze / engage / strategy)
  OBSERVE  → processes tool result, updates state, self-corrects on failure

Self-correction: if a generated reply fails ContentModerator gates
(signal_density or named_role), the agent logs the specific failure,
adjusts its generation strategy, and retries — up to MAX_REGENERATIONS times.

Memory: queries bot.db interactions table before deciding action for each
tweet so the agent avoids replying to the same user twice in one day.
"""

import random
import re
import sqlite3
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from config import Config
from content.content_moderator import ContentModerator
from core.bandit import get_phrase_bandit
from core.error_handler import get_error_handler
from core.policy import get_policy_engine
from core.rate_limiter import get_rate_limiter
from core.reward_aggregator import RewardAggregator
from db.schema import DB_PATH
from feedback import FeedbackTracker
from logger_setup import log
from search.search_tweets import search_tweets
from utils.human_behavior import natural_scroll
from utils.intent_scorer import get_intent_label, score_intent

# Maximum self-correction attempts before giving up on a reply
MAX_REGENERATIONS = 3

# ANSI escape codes for structured ReAct console output
_C = {
    "THOUGHT": "\033[36m",   # Cyan
    "ACTION":  "\033[33m",   # Yellow
    "OBSERVE": "\033[32m",   # Green
    "WARN":    "\033[31m",   # Red
    "RESET":   "\033[0m",
}


def _fmt(label: str, text: str) -> str:
    color = _C.get(label, "")
    return f"{color}[{label:<7}] {text}{_C['RESET']}"


# ---------------------------------------------------------------------------
# Moderation analysis helper
# ---------------------------------------------------------------------------

def _analyze_reply(text: str) -> Dict[str, Any]:
    """
    Run all ContentModerator gates and return structured diagnosis.

    Returns:
        passed        — True if all gates passed and text is post-ready
        gate_failed   — name of the first hard failure (or None)
        signal_score  — int 0-4 from signal_density()
        has_role      — bool from has_named_role()
        quality       — float from score_quality()
        is_generic    — bool
        soft_failures — list of soft gate names that failed (for self-correction log)
    """
    if not text or not text.strip():
        return {"passed": False, "gate_failed": "empty", "signal_score": 0,
                "has_role": False, "quality": 0.0, "is_generic": True, "soft_failures": []}

    is_valid, reason = ContentModerator.validate(text)
    if not is_valid:
        return {"passed": False, "gate_failed": reason, "signal_score": 0,
                "has_role": False, "quality": 0.0, "is_generic": True, "soft_failures": []}

    signal = ContentModerator.signal_density(text)
    has_role = ContentModerator.has_named_role(text)
    is_gen = ContentModerator.is_generic(text)
    quality = ContentModerator.score_quality(text)

    soft_failures = []
    if signal < 2:
        soft_failures.append("signal_density")
    if not has_role:
        soft_failures.append("named_role")
    if is_gen:
        soft_failures.append("generic")

    passed = not is_gen and quality >= 0.45
    return {
        "passed": passed,
        "gate_failed": None,
        "signal_score": signal,
        "has_role": has_role,
        "quality": quality,
        "is_generic": is_gen,
        "soft_failures": soft_failures,
    }


# ---------------------------------------------------------------------------
# AgentController
# ---------------------------------------------------------------------------

class AgentController:
    """
    Autonomous ReAct agent for one engagement cycle.

    Lifecycle:
        ctrl = AgentController(page, feedback_tracker)
        success = ctrl.run_cycle(keyword=None)
        ctrl.close()  # only needed if you did not pass a feedback_tracker
    """

    def __init__(self, page, feedback_tracker: Optional[FeedbackTracker] = None):
        self.page = page
        self.rate_limiter = get_rate_limiter()
        self.error_handler = get_error_handler()

        # Lazy-import content engine to avoid circular imports at module load
        from content.engine import get_content_engine
        self.content_engine = get_content_engine()

        self.feedback_tracker = feedback_tracker or FeedbackTracker()
        self._owns_feedback = feedback_tracker is None

        # Cycle-scoped counters
        self._actions = 0
        self._errors = 0
        self._high_intent = 0

    # ------------------------------------------------------------------
    # Logging — structured ReAct output
    # ------------------------------------------------------------------

    def _thought(self, text: str) -> None:
        log.info(_fmt("THOUGHT", text))

    def _act(self, tool: str, args: str = "") -> None:
        suffix = f"({args})" if args else "()"
        log.info(_fmt("ACTION", f"{tool}{suffix}"))

    def _observe(self, text: str) -> None:
        log.info(_fmt("OBSERVE", text))

    def _warn(self, text: str) -> None:
        log.warning(_fmt("WARN", text))

    # ------------------------------------------------------------------
    # Tool: strategy_lookup_tool
    # Fetches smoothed Bandit rewards + rate status snapshot.
    # ------------------------------------------------------------------

    def strategy_lookup_tool(self) -> Dict[str, Any]:
        """
        Returns a strategy snapshot with:
          style_rewards    — smoothed Bayesian score per reply style
          keyword_rewards  — conversion_yield per search phrase
          rate_remaining   — remaining daily actions per type
          rate_pressure    — float 0-1 (how close we are to daily limits)
          recommended_style / recommended_phrase
        """
        self._act("strategy_lookup_tool")
        try:
            agg = RewardAggregator()
            style_stats = agg.get_by_style()
            keyword_stats = agg.get_by_keyword()
            remaining = self.rate_limiter.get_remaining_actions()

            daily_caps = {
                "reply":  getattr(Config, "DAILY_REPLY_LIMIT",   Config.RATE_LIMITS.get("reply",   {}).get("daily", 15)),
                "follow": getattr(Config, "DAILY_FOLLOW_LIMIT",  Config.RATE_LIMITS.get("follow",  {}).get("daily", 10)),
                "like":   getattr(Config, "DAILY_LIKE_LIMIT",    Config.RATE_LIMITS.get("like",    {}).get("daily", 20)),
                "quote":  getattr(Config, "DAILY_QUOTE_LIMIT",   Config.RATE_LIMITS.get("quote",   {}).get("daily", 2)),
            }
            total_cap = sum(daily_caps.values())
            total_rem = sum(remaining.get(k, 0) for k in daily_caps)
            rate_pressure = 1.0 - (total_rem / max(total_cap, 1))

            best_style = (
                max(style_stats, key=lambda s: style_stats[s].get("smoothed_score", 0))
                if style_stats else "grok"
            )
            best_phrase = (
                max(keyword_stats, key=lambda k: keyword_stats[k].get("conversion_yield", 0))
                if keyword_stats else None
            )

            snap = {
                "style_rewards":    {s: style_stats[s].get("smoothed_score", 0.0) for s in style_stats},
                "keyword_rewards":  {k: keyword_stats[k].get("conversion_yield", 0.0) for k in keyword_stats},
                "rate_remaining":   remaining,
                "rate_pressure":    rate_pressure,
                "recommended_style": best_style,
                "recommended_phrase": best_phrase,
            }
            self._observe(
                f"Rate remaining={remaining} | pressure={rate_pressure:.0%} | "
                f"best_style={best_style} | best_phrase={best_phrase!r}"
            )
            return snap

        except Exception as exc:
            log.debug(f"strategy_lookup_tool error: {exc}")
            remaining = self.rate_limiter.get_remaining_actions()
            return {
                "style_rewards": {}, "keyword_rewards": {},
                "rate_remaining": remaining, "rate_pressure": 0.0,
                "recommended_style": "grok", "recommended_phrase": None,
            }

    # ------------------------------------------------------------------
    # Tool: search_tool
    # Returns (tweet_elements, phrase_actually_used) with 3-tier fallback.
    # ------------------------------------------------------------------

    def search_tool(self, query: str) -> Tuple[List[Any], str]:
        self._act("search_tool", f"query={query!r}")

        tweets = search_tweets(self.page, query)
        if tweets:
            self._observe(f"Found {len(tweets)} tweets for {query!r}")
            return tweets, query

        words = query.split()
        if len(words) > 2:
            simplified = " ".join(words[1:])
            self._thought(f"No results for {query!r}. Trying simplified: {simplified!r}")
            tweets = search_tweets(self.page, simplified)
            if tweets:
                self._observe(f"Found {len(tweets)} tweets for simplified {simplified!r}")
                return tweets, simplified

        backup = self._choose_search_phrase(exclude=query)
        if backup and backup != query:
            self._thought(f"Still no results. Trying backup phrase {backup!r}")
            tweets = search_tweets(self.page, backup)
            if tweets:
                self._observe(f"Found {len(tweets)} tweets for backup {backup!r}")
                return tweets, backup

        self._observe(f"No tweets found after all fallbacks for {query!r}")
        return [], query

    # ------------------------------------------------------------------
    # Tool: analyze_intent_tool
    # Multi-pass intent scoring with optional LLM override for boundary cases.
    # ------------------------------------------------------------------

    def analyze_intent_tool(self, tweet_text: str) -> Dict[str, Any]:
        self._act("analyze_intent_tool", f"text={tweet_text[:50]!r}...")

        try:
            raw_score = score_intent(tweet_text)
            intent_label = get_intent_label(raw_score)
            llm_override = False

            # LLM override for boundary tweets (intent score == 2 / MEDIUM)
            if raw_score == 2 and getattr(Config, "REFLECTION_ENABLED", True):
                try:
                    from utils.llm_intent_scorer import get_llm_intent_scorer
                    llm_scorer = get_llm_intent_scorer()
                    llm_result = llm_scorer.score(tweet_text)
                    if llm_result:
                        if llm_result.get("negation_check"):
                            raw_score = min(raw_score, 1)
                            intent_label = get_intent_label(raw_score)
                            llm_override = True
                        elif "intent_score" in llm_result and llm_result["intent_score"] != raw_score:
                            raw_score = llm_result["intent_score"]
                            intent_label = get_intent_label(raw_score)
                            llm_override = True
                except Exception:
                    pass

            self._observe(
                f"Intent={intent_label} (score={raw_score}"
                + (" LLM-override" if llm_override else "") + ")"
            )
            return {"intent_score": raw_score, "intent_label": intent_label, "llm_override": llm_override}

        except Exception as exc:
            log.debug(f"analyze_intent_tool error: {exc}")
            return {"intent_score": 1, "intent_label": "LOW", "llm_override": False}

    # ------------------------------------------------------------------
    # Tool: engagement_action_tool
    # Routes to the appropriate sub-action; enforces rate limits first.
    # ------------------------------------------------------------------

    def engagement_action_tool(
        self,
        action_type: str,
        tweet: Any,
        phrase: str = "",
        intent_score: int = 1,
        intent_label: str = "LOW",
        reflection: str = "",
        style_weights: Optional[Dict[str, float]] = None,
    ) -> Dict[str, Any]:
        self._act("engagement_action_tool", f"action={action_type}")

        # Rate limit is inviolable — checked before every action
        if action_type not in ("scroll_timeline", "take_break"):
            can_act, limit_reason = self.rate_limiter.can_perform_action(action_type)
            if not can_act:
                self._observe(f"Rate limit blocks '{action_type}': {limit_reason}")
                return {"success": False, "action_type": action_type, "blocked_by": "rate_limit"}

        if action_type == "reply":
            return self._do_reply(tweet, phrase, intent_score, intent_label, reflection, style_weights)
        if action_type == "follow":
            return self._do_follow(tweet, intent_label)
        if action_type == "like":
            return self._do_like(tweet)
        if action_type == "quote":
            return self._do_quote(tweet, phrase)
        if action_type == "scroll_timeline":
            return self._do_scroll()
        if action_type == "take_break":
            return self._do_break()

        return {"success": False, "action_type": action_type, "error": f"unknown:{action_type}"}

    # ------------------------------------------------------------------
    # Reply with self-correction loop
    # ------------------------------------------------------------------

    def _do_reply(
        self,
        tweet: Any,
        phrase: str,
        intent_score: int,
        intent_label: str,
        reflection: str,
        style_weights: Optional[Dict[str, float]],
    ) -> Dict[str, Any]:
        """
        Generate a reply, run ContentModerator gates, and self-correct up to
        MAX_REGENERATIONS times if signal_density or named_role gates fail.
        """
        from core.reply_handler import _attempt_reply
        from core.generator import generate_contextual_reply

        use_curiosity = intent_score >= 2
        tweet_text = self._extract_text(tweet)

        style_sequence = self._rank_styles(intent_score)
        last_failure = "unknown"

        for attempt in range(MAX_REGENERATIONS):
            style = style_sequence[attempt % len(style_sequence)]

            if attempt > 0:
                self._thought(
                    f"Self-correction attempt {attempt + 1}/{MAX_REGENERATIONS}. "
                    f"Last failure: '{last_failure}'. Trying style={style!r}."
                )

            # --- Generate candidate reply ----------------------------------
            candidate = self._generate_candidate(tweet_text, style, reflection, last_failure, attempt)

            if not candidate:
                last_failure = "empty_generation"
                continue

            candidate = ContentModerator.sanitize_output(candidate)
            diagnosis = _analyze_reply(candidate)

            if not diagnosis["passed"]:
                last_failure = (
                    diagnosis["gate_failed"]
                    or (", ".join(diagnosis["soft_failures"]) if diagnosis["soft_failures"] else "quality")
                )
                self._thought(
                    f"ContentModerator FAILED — gates: {last_failure} | "
                    f"signal_density={diagnosis['signal_score']}/4 | "
                    f"has_named_role={diagnosis['has_role']} | "
                    f"quality={diagnosis['quality']:.2f} | "
                    f"is_generic={diagnosis['is_generic']}"
                )
                continue

            # --- Passed moderation: post it -------------------------------
            self._observe(
                f"Moderation PASSED (style={style}, quality={diagnosis['quality']:.2f}, "
                f"signal={diagnosis['signal_score']}/4, has_role={diagnosis['has_role']})"
            )

            from actions.reply import reply_tweet
            success, reply_id = reply_tweet(self.page, tweet, candidate)

            if success:
                self.rate_limiter.record_action("reply", success=True, target_id=reply_id)
                self.error_handler.reset_error_counter()
                self._actions += 1
                self._observe(f"Reply posted [style={style}] | reply_id={reply_id or 'unknown'}")

                # Feedback logging (single source of truth)
                self._log_feedback(tweet, tweet_text, candidate, reply_id, intent_label, style, reflection)
                return {"success": True, "action_type": "reply", "style": style, "reply_id": reply_id}

            self.rate_limiter.record_action("reply", success=False)
            last_failure = "post_failed"

        self._warn(f"Reply self-correction exhausted ({MAX_REGENERATIONS} attempts). Last: {last_failure}")
        return {"success": False, "action_type": "reply", "error": last_failure}

    def _generate_candidate(self, tweet_text: str, style: str, reflection: str,
                             last_failure: str, attempt: int) -> str:
        """
        Generate a reply candidate, adding correction guidance on retry attempts.
        Returns raw text (caller sanitizes).
        """
        from core.generator import generate_contextual_reply

        # Build correction hint so the LLM addresses the specific gate failure
        correction = ""
        if attempt > 0:
            if "signal_density" in last_failure:
                correction = (
                    " Include a specific tool (e.g. n8n, Zapier, Python), a number, "
                    "and a concrete outcome or consequence."
                )
            elif "named_role" in last_failure:
                correction = (
                    " Reference a specific role: founder, VA, junior dev, CFO, "
                    "recruiter, or client."
                )
            elif "generic" in last_failure:
                correction = (
                    " Avoid generic filler. Make a specific, direct observation "
                    "about the real-world implication."
                )

        try:
            if style == "grok" and getattr(Config, "GROK_STYLE", True):
                user_msg = (
                    f'Reply to this tweet from someone who needs real help:\n\n'
                    f'"{tweet_text}"'
                )
                if reflection:
                    user_msg += f"\n\nContext: {reflection}"
                if correction:
                    user_msg += f"\n\nIMPORTANT correction for this attempt:{correction}"
                return generate_contextual_reply(
                    tweet_text=tweet_text,
                    system_prompt=Config.GROK_SYSTEM_INSTRUCTION,
                    user_message=user_msg,
                )

            if style == "curiosity":
                result = self.content_engine.generate_curiosity_reply(tweet_text)
                return result.text if result else ""

            # standard
            result = self.content_engine.generate_reply(tweet_text)
            return result.text if result else ""

        except Exception as exc:
            log.debug(f"_generate_candidate error (style={style}): {exc}")
            return ""

    def _rank_styles(self, intent_score: int) -> List[str]:
        """Return style priority list for self-correction cycling."""
        if intent_score >= 3:
            return ["grok", "curiosity", "standard"]
        if intent_score == 2:
            return ["curiosity", "grok", "standard"]
        return ["standard", "curiosity"]

    def _log_feedback(self, tweet, tweet_text, reply_text, reply_id,
                      intent_label, style, reflection):
        try:
            tweet_id = ""
            link = tweet.locator("a[href*='/status/']").first
            if link.count() > 0:
                m = re.search(r"/status/(\d+)", link.get_attribute("href") or "")
                if m:
                    tweet_id = m.group(1)

            user_handle = ""
            author = tweet.locator("a[role='link'][href^='/']").first
            if author.count() > 0:
                href = author.get_attribute("href") or ""
                candidate = href.lstrip("/").split("/")[0]
                if candidate and candidate not in ("i", "home", "explore"):
                    user_handle = candidate

            self.feedback_tracker.log_reply(
                tweet_id=tweet_id,
                reply_id=reply_id or "",
                user_handle=user_handle,
                tweet_text=tweet_text,
                reply_text=reply_text,
                intent=intent_label,
                reply_style=style,
                reflection_summary=reflection,
            )
        except Exception as exc:
            log.debug(f"Feedback log failed: {exc}")

    # ------------------------------------------------------------------
    # Other action sub-tools
    # ------------------------------------------------------------------

    def _do_follow(self, tweet: Any, intent_label: str) -> Dict[str, Any]:
        try:
            from core.follow_handler import _attempt_follow
            actions, errors = _attempt_follow(
                tweet, self.rate_limiter, self.error_handler, intent_label, self.feedback_tracker
            )
            if actions:
                self._actions += actions
                self._observe("Follow succeeded")
                return {"success": True, "action_type": "follow"}
            self._observe("Follow skipped or failed")
            return {"success": False, "action_type": "follow"}
        except Exception as exc:
            self._errors += 1
            return {"success": False, "action_type": "follow", "error": str(exc)}

    def _do_like(self, tweet: Any) -> Dict[str, Any]:
        try:
            from actions.like import like_tweet
            success = like_tweet(tweet)
            self.rate_limiter.record_action("like", success=success, target_id=None)
            if success:
                self._actions += 1
            self._observe(f"Like {'succeeded' if success else 'failed'}")
            return {"success": success, "action_type": "like"}
        except Exception as exc:
            self._errors += 1
            return {"success": False, "action_type": "like", "error": str(exc)}

    def _do_quote(self, tweet: Any, phrase: str) -> Dict[str, Any]:
        try:
            from core.quote_handler import _attempt_quote
            actions, errors = _attempt_quote(
                tweet, self.page, self.rate_limiter, self.error_handler, self.content_engine
            )
            if actions:
                self._actions += actions
                self._observe("Quote tweet succeeded")
                return {"success": True, "action_type": "quote"}
            self._observe("Quote tweet skipped or failed")
            return {"success": False, "action_type": "quote"}
        except Exception as exc:
            self._errors += 1
            return {"success": False, "action_type": "quote", "error": str(exc)}

    def _do_scroll(self) -> Dict[str, Any]:
        self._observe("scroll_timeline (low-cost action)")
        try:
            natural_scroll(self.page, pixels=random.randint(400, 900))
            time.sleep(random.uniform(1.0, 2.5))
            return {"success": True, "action_type": "scroll_timeline"}
        except Exception as exc:
            return {"success": False, "action_type": "scroll_timeline", "error": str(exc)}

    def _do_break(self) -> Dict[str, Any]:
        secs = random.uniform(30, 90)
        self._observe(f"take_break for {secs:.0f}s (rate pressure high)")
        time.sleep(secs)
        return {"success": True, "action_type": "take_break", "duration": secs}

    # ------------------------------------------------------------------
    # Memory: check prior interactions with a user handle
    # ------------------------------------------------------------------

    def _check_memory(self, user_handle: str) -> Optional[Dict[str, Any]]:
        """
        Query bot.db to see if we have interacted with this user before.
        Returns dict or None.
        """
        if not user_handle:
            return None
        try:
            conn = sqlite3.connect(str(DB_PATH))
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                """SELECT reply_style, sent_at, outcome_score,
                          got_reply_back, got_follow
                   FROM interactions
                   WHERE user_handle = ?
                   ORDER BY sent_at DESC LIMIT 1""",
                (user_handle,),
            ).fetchone()
            conn.close()

            if row:
                sent_at_str = row["sent_at"]
                try:
                    sent_dt = datetime.fromisoformat(sent_at_str)
                    if sent_dt.tzinfo is None:
                        sent_dt = sent_dt.replace(tzinfo=timezone.utc)
                    days_ago = (datetime.now(timezone.utc) - sent_dt).days
                except Exception:
                    days_ago = 0

                return {
                    "style":          row["reply_style"],
                    "days_ago":       days_ago,
                    "outcome_score":  row["outcome_score"],
                    "got_reply_back": bool(row["got_reply_back"]),
                    "got_follow":     bool(row["got_follow"]),
                }
        except Exception as exc:
            log.debug(f"Memory check failed for @{user_handle}: {exc}")
        return None

    # ------------------------------------------------------------------
    # Decision: choose action given all context
    # ------------------------------------------------------------------

    def _decide_action(
        self,
        intent_score: int,
        policy_probs: Dict[str, float],
        memory: Optional[Dict],
        remaining: Dict[str, int],
        rate_pressure: float,
    ) -> str:
        """
        THOUGHT-level reasoning: choose action type based on:
          - intent score (HIGH=3, MEDIUM=2, LOW=1)
          - PolicyEngine probabilities (evidence-adjusted, MIN floors enforced by policy)
          - memory of prior user interactions
          - current rate limit pressure

        Inviolable floors (MIN_REPLY_PROB) are enforced by the PolicyEngine upstream.
        Here we only route, never override safety floors downward.
        """
        # High rate pressure → conserve limits
        if rate_pressure > 0.85:
            self._thought(
                f"Rate pressure {rate_pressure:.0%} is HIGH. Choosing scroll_timeline to conserve limits."
            )
            return "scroll_timeline"

        # Memory-driven override — avoid double-replying on same day
        if memory:
            if memory["days_ago"] == 0:
                self._thought(
                    f"Memory: already replied to this user today (style={memory['style']}). "
                    "Switching to 'follow' to avoid repeat contact."
                )
                if remaining.get("follow", 0) > 0:
                    return "follow"
                return "scroll_timeline"

            if memory.get("got_reply_back"):
                self._thought(
                    "Memory: user replied to us — warm lead. Boosting reply selection."
                )
                policy_probs = {
                    **policy_probs,
                    "reply_probability": min(0.92, policy_probs.get("reply_probability", 0.5) * 1.5),
                }

        reply_prob = policy_probs.get("reply_probability", Config.REPLY_PROBABILITY)
        follow_prob = policy_probs.get("follow_probability", Config.FOLLOW_PROBABILITY)
        quote_prob = policy_probs.get("quote_probability", 0.05)
        roll = random.random()

        if intent_score >= 3:   # HIGH
            if roll < reply_prob and remaining.get("reply", 0) > 0:
                return "reply"
            if roll < reply_prob + quote_prob and remaining.get("quote", 0) > 0:
                return "quote"
            if remaining.get("follow", 0) > 0:
                return "follow"
            if remaining.get("like", 0) > 0:
                return "like"
            return "scroll_timeline"

        if intent_score == 2:   # MEDIUM
            if roll < follow_prob and remaining.get("follow", 0) > 0:
                return "follow"
            if roll < follow_prob + reply_prob * 0.5 and remaining.get("reply", 0) > 0:
                return "reply"
            if remaining.get("like", 0) > 0:
                return "like"
            return "scroll_timeline"

        # LOW — inviolable MIN_REPLY_PROB floor to feed the learning loop
        min_floor = getattr(Config, "MIN_REPLY_PROB", 0.15)
        if roll < min_floor and remaining.get("reply", 0) > 0:
            return "reply"
        if roll < 0.40 and remaining.get("like", 0) > 0:
            return "like"
        return "scroll_timeline"

    # ------------------------------------------------------------------
    # Search phrase selection (bandit-driven, 75/25 split)
    # ------------------------------------------------------------------

    def _choose_search_phrase(
        self,
        strategy: Optional[Dict] = None,
        exclude: Optional[str] = None,
    ) -> str:
        intent_kw = [k for k in getattr(Config, "INTENT_KEYWORDS", []) if k != exclude]

        if intent_kw and random.random() < 0.75:
            chosen = random.choice(intent_kw)
            self._thought(f"Search phrase: {chosen!r} (75% intent-targeted path)")
            return chosen

        phrases = getattr(Config, "SEARCH_PHRASES", None) or (
            getattr(Config, "SEARCH_KEYWORDS", []) + getattr(Config, "INTENT_KEYWORDS", [])
        )
        candidates = [p for p in phrases if p != exclude] or phrases or ["need more clients"]

        if strategy and strategy.get("recommended_phrase") in candidates:
            rec = strategy["recommended_phrase"]
            yield_ = strategy["keyword_rewards"].get(rec, 0.0)
            self._thought(
                f"Bandit recommends {rec!r} (conversion_yield={yield_:.3f})"
            )

        try:
            bandit = get_phrase_bandit(candidates)
            chosen = bandit.select()
            self._thought(f"Search phrase: {chosen!r} (25% UCB1 bandit path)")
            return chosen
        except Exception as exc:
            log.debug(f"Phrase bandit failed: {exc}")
            return random.choice(candidates)

    # ------------------------------------------------------------------
    # Tweet element helpers
    # ------------------------------------------------------------------

    def _extract_text(self, tweet) -> str:
        try:
            from utils.tweet_text import get_tweet_text, clean_tweet_text
            raw = get_tweet_text(tweet) or ""
            cleaned = clean_tweet_text(raw)
            return cleaned or raw
        except Exception:
            return ""

    def _extract_handle(self, tweet) -> Optional[str]:
        try:
            author = tweet.locator("a[role='link'][href^='/']").first
            if author.count() > 0:
                href = author.get_attribute("href") or ""
                candidate = href.lstrip("/").split("/")[0]
                if candidate and candidate not in ("i", "home", "explore"):
                    return candidate
        except Exception:
            pass
        return None

    # ------------------------------------------------------------------
    # Main ReAct cycle
    # ------------------------------------------------------------------

    def run_cycle(self, keyword: Optional[str] = None) -> bool:
        """
        Execute one full ReAct cycle: strategy → search → per-tweet loop.
        Returns True if at least one action was taken.
        """
        self._actions = self._errors = self._high_intent = 0

        log.info("=" * 70)
        log.info("AGENT CYCLE STARTING  [ReAct mode — AgentController]")
        log.info("=" * 70)

        # ── Pre-flight ───────────────────────────────────────────────────────
        self._thought("Pre-flight: checking detection cooldown.")
        if self.error_handler.is_in_detection_cooldown():
            self._warn("Detection cooldown active — aborting cycle.")
            return False

        # ── STRATEGY: snapshot rewards + rate state ──────────────────────────
        strategy = self.strategy_lookup_tool()
        remaining = strategy["rate_remaining"]
        rate_pressure = strategy["rate_pressure"]

        if sum(remaining.values()) == 0:
            self._thought("All daily limits exhausted. No actions possible today.")
            return False

        if rate_pressure > 0.85:
            self._thought(
                f"Rate pressure {rate_pressure:.0%} is very high. "
                "Will prefer scroll / low-cost actions this cycle."
            )

        # ── Choose search phrase ─────────────────────────────────────────────
        self._thought("Consulting bandit rewards and intent keyword pool for search phrase.")
        phrase = keyword or self._choose_search_phrase(strategy=strategy)

        # ── ACTION: search_tool ──────────────────────────────────────────────
        tweets, phrase_used = self.search_tool(phrase)
        if not tweets:
            self._thought("No tweets found after all fallbacks. Ending cycle early.")
            try:
                from database import log_search
                log_search(phrase_used, tweets_found=0)
            except Exception:
                pass
            return False

        self._thought(
            f"Found {len(tweets)} tweets for {phrase_used!r}. "
            "Will analyze intent and choose an engagement action for each."
        )

        first_tweet = tweets[0]

        # ── Per-tweet ReAct sub-loop ─────────────────────────────────────────
        for idx, tweet in enumerate(tweets, 1):
            self._thought(f"— Tweet {idx}/{len(tweets)} —")

            tweet_text = self._extract_text(tweet)
            user_handle = self._extract_handle(tweet)

            # ACTION: analyze_intent_tool
            intent_info = self.analyze_intent_tool(tweet_text)
            intent_score = intent_info["intent_score"]
            intent_label = intent_info["intent_label"]

            if intent_score >= 3:
                self._high_intent += 1

            # Memory check
            memory = None
            if user_handle:
                memory = self._check_memory(user_handle)
                if memory:
                    self._thought(
                        f"Memory: @{user_handle} — last reply {memory['days_ago']}d ago, "
                        f"style={memory['style']}, "
                        f"got_reply_back={memory['got_reply_back']}, "
                        f"outcome={memory['outcome_score']}"
                    )
                else:
                    self._thought(f"Memory: no prior interaction with @{user_handle}.")

            # Policy probabilities
            try:
                policy = get_policy_engine()
                from utils.tweet_metrics import get_tweet_metrics
                from utils.engagement_score import score_tweet
                metrics = get_tweet_metrics(tweet)
                eng_score = score_tweet(metrics)
                import time as _t
                policy_probs = policy.get_action_probabilities({
                    "intent": intent_score,
                    "keyword": phrase_used,
                    "engagement_score": eng_score,
                    "time_hour": _t.gmtime().tm_hour,
                })
            except Exception:
                policy_probs = {
                    "reply_probability":  Config.REPLY_PROBABILITY,
                    "follow_probability": Config.FOLLOW_PROBABILITY,
                    "quote_probability":  0.05,
                    "reply_style_weights": {},
                }

            # Refresh remaining after each action
            remaining = self.rate_limiter.get_remaining_actions()

            self._thought(
                f"Intent={intent_label} | "
                f"policy: reply={policy_probs.get('reply_probability', 0):.2f}, "
                f"follow={policy_probs.get('follow_probability', 0):.2f} | "
                f"remaining: replies={remaining.get('reply', 0)}, "
                f"follows={remaining.get('follow', 0)}"
            )

            # Decision
            action = self._decide_action(
                intent_score, policy_probs, memory, remaining, rate_pressure
            )
            self._thought(f"Decision: execute '{action}' on this tweet.")

            # LLM reflection summary for grok-style replies
            reflection = ""
            if intent_score >= 3 and getattr(Config, "REFLECTION_ENABLED", True):
                try:
                    from utils.llm_intent_scorer import get_llm_intent_scorer
                    lr = get_llm_intent_scorer().score(tweet_text)
                    if lr:
                        pts = lr.get("pain_points", [])
                        reason = lr.get("reason", "")
                        reflection = f"Pain: {', '.join(pts)}. {reason}" if pts else reason
                except Exception:
                    pass

            # ACTION: engagement_action_tool
            result = self.engagement_action_tool(
                action_type=action,
                tweet=tweet,
                phrase=phrase_used,
                intent_score=intent_score,
                intent_label=intent_label,
                reflection=reflection,
                style_weights=policy_probs.get("reply_style_weights"),
            )

            # OBSERVATION
            if result.get("success"):
                self._observe(f"Action '{action}' succeeded.")
                remaining = self.rate_limiter.get_remaining_actions()
            else:
                err = result.get("error") or result.get("blocked_by", "unknown")
                self._observe(f"Action '{action}' failed: {err}")
                if "rate_limit" in str(err):
                    self._thought(
                        "Rate limit hit mid-cycle. Switching to scroll_timeline for remainder."
                    )
                    self._do_scroll()
                    break
                self._errors += 1

            time.sleep(random.uniform(1.0, 3.0))

        # ── Inviolable floor: forced fallback reply ──────────────────────────
        if self._actions == 0 and first_tweet is not None:
            can_reply, _ = self.rate_limiter.can_perform_action("reply")
            if can_reply:
                self._thought(
                    "INVIOLABLE FLOOR: Zero actions taken this cycle. "
                    "Forcing 1 reply on first tweet to maintain learning signal "
                    "(MIN_REPLY_PROB cannot be reasoned away)."
                )
                result = self.engagement_action_tool(
                    action_type="reply",
                    tweet=first_tweet,
                    phrase=phrase_used,
                    intent_score=1,
                    intent_label="LOW",
                )
                self._observe(
                    f"Forced fallback reply {'succeeded' if result.get('success') else 'failed'}."
                )

        # ── Cycle summary ────────────────────────────────────────────────────
        try:
            from database import log_search
            log_search(phrase_used, len(tweets), self._actions, self._high_intent)
        except Exception:
            pass

        log.info(
            f"\n[AGENT] CYCLE COMPLETE — "
            f"{self._actions} actions | {self._errors} errors | "
            f"{self._high_intent} high-intent tweets\n"
        )
        return self._actions > 0

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def close(self) -> None:
        if self._owns_feedback and self.feedback_tracker:
            self.feedback_tracker.close()
