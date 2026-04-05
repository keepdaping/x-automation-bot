"""
RewardAggregator — reads interactions + search_log and returns performance stats.

Used by:
  PolicyEngine  → to bias action probabilities
  LearningLoop  → to push rewards into bandits
  Dashboard     → to surface what's working

All queries are read-only. No writes happen here.
"""

import sqlite3
from typing import Dict

from db.schema import DB_PATH
from logger_setup import log

# Minimum browser-confirmed samples before an average is considered reliable.
# Raised from 3 → 10: small-N averages have very high variance.  With 3 samples,
# one DM can shift avg_outcome_score from 0.0 to 1.67 — a policy-altering jump.
# At 10 samples the standard error of the mean is ~3× smaller.
MIN_SAMPLES = 10

# Bayesian prior used to smooth early estimates before MIN_SAMPLES is reached.
# When a style has N < MIN_SAMPLES interactions, its "reported" avg is blended
# toward this neutral prior.  Prevents cold-start wild swings.
# Set equal to a "mediocre but not terrible" outcome — roughly half a reply-back.
_PRIOR_SCORE  = 0.15   # pseudo-observation value
_PRIOR_WEIGHT = 5      # equivalent to 5 prior observations


def _bayesian_smooth(raw_avg: float, n: int, prior: float = _PRIOR_SCORE, weight: int = _PRIOR_WEIGHT) -> float:
    """
    Bayesian (Laplace-style) smoothing.

    Blends the observed average toward a neutral prior when N is small:
        smoothed = (n * raw_avg + weight * prior) / (n + weight)

    As n → ∞ the prior becomes irrelevant.  At n=0 (never seen) the
    smoothed value equals the prior.  At n=weight the prior contributes 50%.
    """
    return (n * raw_avg + weight * prior) / (n + weight)


class RewardAggregator:

    # ─── By reply style ───────────────────────────────────────────────────

    def get_by_style(self, days: int = 14) -> Dict[str, dict]:
        """
        Returns performance grouped by reply_style.

        {
          "grok":      {"trials": 12, "avg_outcome_score": 0.42, "reply_rate": 0.25, "dm_rate": 0.08},
          "curiosity": {...},
          "standard":  {...},
        }
        """
        conn = sqlite3.connect(str(DB_PATH))
        try:
            cur = conn.execute(
                """
                SELECT reply_style,
                       COUNT(*)              AS trials,
                       AVG(outcome_score)    AS avg_score,
                       AVG(got_reply_back)   AS reply_rate,
                       AVG(got_follow)       AS follow_rate,
                       AVG(got_dm)           AS dm_rate
                FROM interactions
                WHERE sent_at > datetime('now', ?)
                  AND reply_style NOT IN ('follow', '')
                  AND checked_at IS NOT NULL
                GROUP BY reply_style
                """,
                (f"-{days} days",),
            )
            result = {}
            for r in cur.fetchall():
                n        = r[1]
                raw_avg  = r[2] or 0.0
                smoothed = _bayesian_smooth(raw_avg, n)
                result[r[0]] = {
                    "trials":              n,
                    "avg_outcome_score":   round(raw_avg,  4),   # raw (for logging)
                    "smoothed_score":      round(smoothed, 4),   # Bayesian-smoothed (for decisions)
                    "reply_rate":          round(r[3] or 0.0, 4),
                    "follow_rate":         round(r[4] or 0.0, 4),
                    "dm_rate":             round(r[5] or 0.0, 4),
                    "data_confidence":     round(min(1.0, n / MIN_SAMPLES), 2),
                }
            return result
        except Exception as e:
            log.warning(f"[RewardAggregator] get_by_style failed: {e}")
            return {}
        finally:
            conn.close()

    # ─── By intent level ──────────────────────────────────────────────────

    def get_by_intent(self, days: int = 14) -> Dict[str, dict]:
        """
        Returns performance grouped by intent label (HIGH / MEDIUM / LOW).

        {
          "HIGH":   {"trials": 20, "avg_outcome_score": 0.55},
          "MEDIUM": {...},
          "LOW":    {...},
        }
        """
        conn = sqlite3.connect(str(DB_PATH))
        try:
            cur = conn.execute(
                """
                SELECT intent,
                       COUNT(*)           AS trials,
                       AVG(outcome_score) AS avg_score
                FROM interactions
                WHERE sent_at > datetime('now', ?)
                  AND intent IS NOT NULL AND intent != ''
                  AND checked_at IS NOT NULL
                GROUP BY intent
                """,
                (f"-{days} days",),
            )
            return {
                r[0]: {
                    "trials":            r[1],
                    "avg_outcome_score": round(r[2] or 0.0, 4),
                }
                for r in cur.fetchall()
            }
        except Exception as e:
            log.warning(f"[RewardAggregator] get_by_intent failed: {e}")
            return {}
        finally:
            conn.close()

    # ─── By search phrase ─────────────────────────────────────────────────

    def get_by_keyword(self, days: int = 14) -> Dict[str, dict]:
        """
        Returns phrase performance from search_log.
        Uses high_intent_found + actions_taken as a conversion-yield proxy
        (direct outcome_score correlation isn't possible without phrase stored in interactions).

        {
          "need more clients": {
              "searches": 5,
              "avg_tweets_found": 3.2,
              "avg_high_intent": 1.4,
              "avg_actions": 2.1,
              "conversion_yield": 0.87,   # high_intent*2 + actions*0.5 / searches
          },
          ...
        }
        """
        conn = sqlite3.connect(str(DB_PATH))
        try:
            cur = conn.execute(
                """
                SELECT phrase,
                       COUNT(*)                  AS searches,
                       AVG(tweets_found)         AS avg_tweets,
                       AVG(high_intent_found)    AS avg_high_intent,
                       AVG(actions_taken)        AS avg_actions,
                       SUM(high_intent_found)    AS total_high_intent,
                       SUM(actions_taken)        AS total_actions
                FROM search_log
                WHERE timestamp > datetime('now', ?)
                GROUP BY phrase
                HAVING searches >= 1
                """,
                (f"-{days} days",),
            )
            result = {}
            for r in cur.fetchall():
                phrase, searches, avg_tweets, avg_hi, avg_act, total_hi, total_act = r
                searches = max(searches, 1)
                conversion_yield = min(
                    3.0,
                    ((total_hi or 0) * 2.0 + (total_act or 0) * 0.5) / searches,
                )
                result[phrase] = {
                    "searches":         searches,
                    "avg_tweets_found": round(avg_tweets or 0.0, 2),
                    "avg_high_intent":  round(avg_hi or 0.0, 2),
                    "avg_actions":      round(avg_act or 0.0, 2),
                    "conversion_yield": round(conversion_yield, 3),
                }
            return result
        except Exception as e:
            log.warning(f"[RewardAggregator] get_by_keyword failed: {e}")
            return {}
        finally:
            conn.close()

    # ─── Convenience: best performing style ───────────────────────────────

    def get_best_style(self, min_samples: int = MIN_SAMPLES) -> str:
        """
        Return the reply_style with highest smoothed_score (Bayesian estimate).
        Uses smoothed_score rather than raw avg to avoid early-data bias.
        Falls back to "grok" when no style has reached min_samples.
        """
        stats = self.get_by_style()
        # Use smoothed_score for ranking to handle low-N styles fairly
        if not stats:
            return "grok"
        # Prefer styles with sufficient data; fall back to smoothed estimate for rest
        qualified = {k: v for k, v in stats.items() if v["trials"] >= min_samples}
        pool = qualified if qualified else stats
        return max(pool, key=lambda k: pool[k]["smoothed_score"])


# ─── Singleton ────────────────────────────────────────────────────────────

_aggregator: RewardAggregator = None


def get_reward_aggregator() -> RewardAggregator:
    global _aggregator
    if _aggregator is None:
        _aggregator = RewardAggregator()
    return _aggregator
