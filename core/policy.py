"""
PolicyEngine — replaces hardcoded probabilities in core/pipeline.py.

Reads RewardAggregator data and applies evidence-based adjustments to:
  - reply_probability     (how often to attempt a reply at each intent tier)
  - follow_probability    (how often to follow based on intent)
  - quote_probability     (currently static; wired for future use)
  - reply_style_weights   (relative weights for grok / curiosity / standard)

Design principles:
  1. Always falls back to Config defaults if data is insufficient (< MIN_SAMPLES)
  2. Adjustments are bounded (MAX_BOOST / MAX_PENALTY) to prevent runaway drift
  3. Single call per tweet — results are not cached (cheap DB reads, fresh data)
  4. AGGRESSION_LEVEL from Config acts as a global multiplier on all action probs
"""

import time
from typing import Optional

from config import Config
from logger_setup import log

# Minimum confirmed interactions before we trust the statistics.
# Raised from 5 → 10: with 5 samples the variance is too high — a single lucky
# reply-back can shift style weights by 20%.  10 gives a more stable estimate.
_MIN_SAMPLES = 10

# Maximum shift from baseline probability in either direction.
# Asymmetric intentionally: we boost conservatively but penalise less aggressively,
# because false-negative outcome data (phantom zeros from stale batch checks) is
# more likely than false-positive, so penalising should require stronger evidence.
_MAX_BOOST   = 0.20
_MAX_PENALTY = 0.10

# Thresholds for applying adjustments.
# Raised from (avg > 1.0, avg < 0.3) to reduce sensitivity to noisy early data.
# avg_outcome_score is in [0, 10] but in practice rarely exceeds 5 without DM.
# avg > 1.5 ≈ "reliably generates at least one reply-back per two interactions"
# avg < 0.5 ≈ "almost never gets any response at all"
_BOOST_THRESHOLD   = 1.5
_PENALTY_THRESHOLD = 0.5

# TTL for in-process caching of reward aggregator results.
# The policy is called on every tweet (~10-50 per cycle). Without a cache, each
# cycle triggers 2 × N DB queries where N is tweet count.
# 60 seconds is long enough to serve an entire cycle (~90s) with fresh data
# while being short enough to pick up same-day learning cycle updates promptly.
_CACHE_TTL_SECONDS = 60

# ── Absolute minimum floors (applied AFTER aggression multiplier) ──────────
# These are inviolable: no combination of penalty, aggression, or learning
# collapse can push the bot below these values.  They ensure the bot always
# takes some actions so the learning loop has signal to work with.
_MIN_REPLY_PROB  = 0.15
_MIN_FOLLOW_PROB = 0.05

# Cold-start threshold: if total checked interactions across all intent levels
# is below this number, skip reward-based adjustments entirely and operate on
# pure baseline probabilities with exploration boost.
_COLD_START_THRESHOLD = _MIN_SAMPLES  # 10

# Base probabilities mirror the original hardcoded values exactly
_BASE = {
    3: {"reply": 1.00, "follow": 0.60},
    2: {"reply": 0.30, "follow": 0.30},
    1: {"reply": Config.REPLY_PROBABILITY, "follow": Config.FOLLOW_PROBABILITY},
}


class PolicyEngine:
    """
    Converts (intent, engagement context) → action probabilities.

    get_action_probabilities(context) is the only public method.

    Internal cache:
      Reward-aggregator DB reads are cached for _CACHE_TTL_SECONDS seconds so
      the policy does not hammer SQLite on every single tweet in a cycle.
      The cache is invalidated after TTL expires — guarantees same-cycle
      consistency while staying fresh across cycles.
    """

    def __init__(self):
        self._cached_style_stats: dict = {}
        self._cached_intent_stats: dict = {}
        self._cache_expires_at: float = 0.0

    def _refresh_cache_if_stale(self) -> None:
        if time.time() < self._cache_expires_at:
            return
        try:
            from core.reward_aggregator import get_reward_aggregator
            agg = get_reward_aggregator()
            self._cached_style_stats  = agg.get_by_style(days=14)
            self._cached_intent_stats = agg.get_by_intent(days=14)
            self._cache_expires_at    = time.time() + _CACHE_TTL_SECONDS
            log.debug("[Policy] Cache refreshed")
        except Exception as e:
            log.debug(f"[Policy] Cache refresh failed (non-fatal): {e}")

    def _is_cold_start(self) -> bool:
        """
        True when there is insufficient checked-interaction data to trust learning.

        Uses already-cached stats so this costs no extra DB round-trips.
        Triggers cold-start mode in two cases:
          1. No intent stats at all (no interactions with checked_at set yet).
          2. Total checked trials across all intent levels < threshold — not
             enough observations to distinguish signal from phantom-zero noise.
        """
        if not self._cached_intent_stats:
            return True
        total_trials = sum(v["trials"] for v in self._cached_intent_stats.values())
        return total_trials < _COLD_START_THRESHOLD

    def get_action_probabilities(self, context: dict) -> dict:
        """
        Parameters
        ----------
        context = {
            "intent"           : int   1|2|3,
            "keyword"          : str   search phrase used this cycle,
            "engagement_score" : float virality score,
            "time_hour"        : int   0-23 UTC hour,
        }

        Returns
        -------
        {
            "reply_probability"   : float 0-1,
            "follow_probability"  : float 0-1,
            "quote_probability"   : float 0-1,
            "reply_style_weights" : {"grok": float, "curiosity": float, "standard": float},
        }
        """
        intent = int(context.get("intent", 1))
        intent = max(1, min(3, intent))

        # ── 1. Start from hardcoded baseline ──────────────────────────────
        base = _BASE.get(intent, _BASE[1])
        reply_prob  = base["reply"]
        follow_prob = base["follow"]
        quote_prob  = 0.10

        # ── 2. Uniform style weights (default) ────────────────────────────
        style_weights = {"grok": 1.0, "curiosity": 1.0, "standard": 1.0}

        # ── 3. Apply reward-based adjustment (from TTL-cached aggregator data) ─
        try:
            self._refresh_cache_if_stale()

            # ── Cold-start override ────────────────────────────────────────
            # If there is not enough checked-interaction data, skip all
            # reward-based adjustments and operate on the raw baseline.
            # This prevents phantom-zero penalties from silencing the bot
            # before it has meaningful learning signal.
            if self._is_cold_start():
                log.debug(
                    "[Policy] Cold-start mode — skipping reward adjustments, "
                    "using baseline probabilities with exploration boost"
                )
                # Widen exploration: boost style diversity during cold start
                style_weights = {"grok": 1.5, "curiosity": 1.5, "standard": 1.0}
            else:
                # --- Style weights from past outcome_score ---
                qualified_styles = {
                    k: v for k, v in self._cached_style_stats.items()
                    if v["trials"] >= _MIN_SAMPLES
                }
                if qualified_styles:
                    for style in style_weights:
                        if style in qualified_styles:
                            # Use smoothed_score (Bayesian estimate) rather than raw avg.
                            # smoothed_score pulls toward a neutral prior when N is small,
                            # preventing a single lucky DM from dominating the weights.
                            score = qualified_styles[style].get("smoothed_score",
                                    qualified_styles[style]["avg_outcome_score"])
                            # Additive offset: even a score of 0.0 keeps weight = 0.5.
                            style_weights[style] = max(0.1, score + 0.5)
                    log.debug(f"[Policy] Style weights (smoothed): {style_weights}")

                # --- Reply probability nudge based on intent data ---
                # Only applies to intent < 3 (intent==3 is already 100%).
                # Thresholds are stricter than initial implementation to resist noisy
                # early data and phantom-zero outcomes from stale batch checks.
                if intent < 3:
                    intent_label = {3: "HIGH", 2: "MEDIUM", 1: "LOW"}[intent]
                    stat = self._cached_intent_stats.get(intent_label)
                    if stat and stat["trials"] >= _MIN_SAMPLES:
                        avg = stat["avg_outcome_score"]

                        # Check for all-zero collapse: if avg is zero despite having
                        # data, check whether it's real failure or phantom noise.
                        # Real failure threshold raised: require avg < 0.3 (was 0.5)
                        # to apply penalty, so phantom-zero batch marks don't trigger.
                        if avg > _BOOST_THRESHOLD:
                            # Scale boost linearly: avg=1.5→+0.0, avg=5.0→+MAX_BOOST
                            boost = min(_MAX_BOOST, (avg - _BOOST_THRESHOLD) * 0.04)
                            reply_prob = min(1.0, reply_prob + boost)
                            log.debug(
                                f"[Policy] {intent_label} boosted +{boost:.3f} "
                                f"(avg={avg:.2f}) → reply_prob={reply_prob:.3f}"
                            )
                        elif 0 < avg < _PENALTY_THRESHOLD:
                            # Only penalise when avg is non-zero but below threshold.
                            # avg == 0.0 is treated as "no real signal" and skipped
                            # — zero is the default for unchecked rows, not evidence.
                            penalty = min(_MAX_PENALTY, 0.05)
                            reply_prob = max(_MIN_REPLY_PROB, reply_prob - penalty)
                            log.debug(
                                f"[Policy] {intent_label} penalised -{penalty:.3f} "
                                f"(avg={avg:.2f}) → reply_prob={reply_prob:.3f}"
                            )
                        else:
                            log.debug(
                                f"[Policy] {intent_label} avg={avg:.2f} — "
                                "zero-outcome skipped (may be phantom zeros)"
                            )

        except Exception as e:
            # Non-fatal — degrade gracefully to hardcoded defaults
            log.debug(f"[Policy] Reward adjustment skipped (non-fatal): {e}")

        # ── 4. Global aggression multiplier ───────────────────────────────
        aggression = float(getattr(Config, "AGGRESSION_LEVEL", 1.0))
        reply_prob  = min(1.0, reply_prob  * aggression)
        follow_prob = min(1.0, follow_prob * aggression)

        # ── 5. Absolute minimum floors (post-aggression) ──────────────────
        # Applied AFTER the aggression multiplier so they cannot be overridden
        # by any combination of penalty, multiplier, or configuration.
        # This guarantees the bot always takes some action to generate signal.
        reply_prob  = max(_MIN_REPLY_PROB,  reply_prob)
        follow_prob = max(_MIN_FOLLOW_PROB, follow_prob)

        log.info(
            f"[Policy] intent={intent} → "
            f"reply_prob={reply_prob:.3f}, follow_prob={follow_prob:.3f}, "
            f"cold_start={self._is_cold_start()}"
        )

        return {
            "reply_probability":   reply_prob,
            "follow_probability":  follow_prob,
            "quote_probability":   quote_prob,
            "reply_style_weights": style_weights,
        }


# ─── Singleton ────────────────────────────────────────────────────────────

_engine: Optional[PolicyEngine] = None


def get_policy_engine() -> PolicyEngine:
    global _engine
    if _engine is None:
        _engine = PolicyEngine()
    return _engine
