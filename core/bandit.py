"""
UCB1 Multi-Armed Bandit — adaptive selection without heavy ML.

Algorithm: UCB1 (Upper Confidence Bound)
  score(arm) = avg_reward(arm) + C * sqrt(ln(total_trials) / trials(arm))

Why UCB1 over epsilon-greedy:
  - Automatically reduces exploration as evidence accumulates
  - No hyperparameter tuning (exploration decays naturally)
  - Still guaranteed minimum exploration via epsilon floor

State is persisted in bot.db (bandit_arms table, created lazily).

Instances:
  get_reply_bandit()         → chooses between grok / curiosity / standard
  get_phrase_bandit(phrases) → chooses which search phrase to use
"""

import math
import random
import sqlite3
from typing import List, Optional

from db.schema import DB_PATH
from logger_setup import log

# ─── Constants ────────────────────────────────────────────────────────────

# Sliding-window size per arm.
# Once `trials` exceeds this, the oldest implicit "slot" is discarded on every
# new update so that stale history cannot permanently dominate the average.
# Keeps the bandit responsive to regime changes (e.g. a style that was good in
# week 1 but became irrelevant by week 8).
# Rule of thumb: set to roughly 2× the number of days you want the bandit to
# remember.  30 ≈ one month of daily updates.
_WINDOW_SIZE = 30

# ─── Table creation ───────────────────────────────────────────────────────

_TABLE_CREATED = False


def _ensure_table() -> None:
    global _TABLE_CREATED
    if _TABLE_CREATED:
        return
    conn = sqlite3.connect(str(DB_PATH))
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS bandit_arms (
                namespace    TEXT    NOT NULL,
                arm          TEXT    NOT NULL,
                trials       INTEGER DEFAULT 0,
                total_reward REAL    DEFAULT 0.0,
                PRIMARY KEY (namespace, arm)
            )
        """)
        conn.commit()
        _TABLE_CREATED = True
    finally:
        conn.close()


# ─── UCB1Bandit ───────────────────────────────────────────────────────────

class UCB1Bandit:
    """
    Persistent UCB1 bandit.

    Parameters
    ----------
    namespace       : str   — isolates this bandit from others in the DB
    arms            : list  — the options to choose between
    exploration_c   : float — UCB1 confidence multiplier (higher = more exploration)
    epsilon         : float — minimum exploration floor (always try random arm
                              with this probability, regardless of UCB1 scores)
    """

    def __init__(
        self,
        namespace: str,
        arms: List[str],
        exploration_c: float = 1.0,
        epsilon: float = 0.15,
    ):
        self.namespace = namespace
        self.arms = list(arms)
        self.exploration_c = exploration_c
        self.epsilon = epsilon

        _ensure_table()

        # Register any new arms (INSERT OR IGNORE is idempotent)
        conn = sqlite3.connect(str(DB_PATH))
        try:
            for arm in self.arms:
                conn.execute(
                    "INSERT OR IGNORE INTO bandit_arms (namespace, arm) VALUES (?, ?)",
                    (namespace, arm),
                )
            conn.commit()
        finally:
            conn.close()

    # ─── Core: select ─────────────────────────────────────────────────────

    def select(self) -> str:
        """
        Return the arm to try next.

        Order of decisions:
          1. Epsilon-exploration: random arm with prob=epsilon (anti-exploitation lock-in)
          2. Cold start: untried arms get priority (avoids starving new options)
          3. UCB1: highest upper confidence bound wins
        """
        # 1. Epsilon floor — guaranteed minimum exploration
        if random.random() < self.epsilon:
            chosen = random.choice(self.arms)
            log.debug(f"[Bandit:{self.namespace}] ε-explore → {chosen}")
            return chosen

        state = self._load()
        total_trials = sum(s["trials"] for s in state.values())

        # 2. Cold start — try untested arms before exploiting
        untried = [a for a in self.arms if state.get(a, {}).get("trials", 0) == 0]
        if untried:
            chosen = random.choice(untried)
            log.debug(f"[Bandit:{self.namespace}] cold-start → {chosen}")
            return chosen

        # 3. UCB1 scoring
        scores = {}
        for arm in self.arms:
            s = state.get(arm, {"trials": 1, "total_reward": 0.0})
            n = max(s["trials"], 1)
            avg = s["total_reward"] / n
            confidence = self.exploration_c * math.sqrt(
                math.log(max(total_trials, 1)) / n
            )
            scores[arm] = avg + confidence

        chosen = max(scores, key=lambda a: scores[a])
        log.debug(
            f"[Bandit:{self.namespace}] UCB1 → {chosen} "
            f"(scores={{{', '.join(f'{a}:{v:.3f}' for a,v in scores.items())}}})"
        )
        return chosen

    # ─── Core: update ─────────────────────────────────────────────────────

    def update(self, arm: str, reward: float) -> None:
        """
        Record a reward observation for an arm using a sliding-window approximation.

        Why sliding window?
          Cumulative UCB1 (total_reward / trials) never forgets early data.
          After 60 days, week-1 noise has the same vote as yesterday's signal.
          The sliding window caps effective memory at _WINDOW_SIZE updates so
          the bandit stays responsive to regime changes without a schema change.

        Approximation mechanics:
          While trials < WINDOW_SIZE  → normal cumulative accumulation
          Once  trials >= WINDOW_SIZE → replace the "oldest slot" each update:
            new_total  = old_total * (W-1)/W + reward
            new_trials = W  (stays fixed; prevents UCB confidence from collapsing)

          This is equivalent to an exponential moving average with α = 1/W, which
          gives weight 0.5 to data from W*ln(2) ≈ 21 updates ago.
        """
        if arm not in self.arms:
            log.debug(f"[Bandit:{self.namespace}] unknown arm '{arm}' — skipping")
            return

        conn = sqlite3.connect(str(DB_PATH))
        try:
            # Load current state for this arm only
            cur = conn.execute(
                "SELECT trials, total_reward FROM bandit_arms WHERE namespace = ? AND arm = ?",
                (self.namespace, arm),
            )
            row = cur.fetchone()
            if row is None:
                conn.close()
                return
            n, total = row[0], row[1]

            if n < _WINDOW_SIZE:
                # Accumulation phase — standard UCB1 update
                new_n     = n + 1
                new_total = total + reward
            else:
                # Sliding-window phase — approximate eviction of oldest slot
                new_n     = _WINDOW_SIZE           # trials stays fixed at window size
                new_total = total * (_WINDOW_SIZE - 1) / _WINDOW_SIZE + reward

            conn.execute(
                "UPDATE bandit_arms SET trials = ?, total_reward = ? WHERE namespace = ? AND arm = ?",
                (new_n, new_total, self.namespace, arm),
            )
            conn.commit()
        except Exception as e:
            log.warning(f"[Bandit:{self.namespace}] update failed: {e}")
        finally:
            conn.close()

        log.debug(f"[Bandit:{self.namespace}] update arm={arm} reward={reward:.4f}")

    # ─── Stats ────────────────────────────────────────────────────────────

    def get_stats(self) -> dict:
        """Return current arm statistics for logging / dashboard."""
        state = self._load()
        result = {}
        for arm in self.arms:
            s = state.get(arm, {"trials": 0, "total_reward": 0.0})
            n = max(s["trials"], 1)
            result[arm] = {
                "trials":       s["trials"],
                "avg_reward":   round(s["total_reward"] / n, 4),
                "total_reward": round(s["total_reward"], 4),
            }
        return result

    # ─── Internal ─────────────────────────────────────────────────────────

    def _load(self) -> dict:
        conn = sqlite3.connect(str(DB_PATH))
        try:
            cur = conn.execute(
                "SELECT arm, trials, total_reward FROM bandit_arms WHERE namespace = ?",
                (self.namespace,),
            )
            return {r[0]: {"trials": r[1], "total_reward": r[2]} for r in cur.fetchall()}
        finally:
            conn.close()


# ─── Singletons ───────────────────────────────────────────────────────────

_reply_bandit: Optional[UCB1Bandit] = None
_phrase_bandit: Optional[UCB1Bandit] = None
_phrase_bandit_arms: Optional[frozenset] = None


def get_reply_bandit() -> UCB1Bandit:
    """
    Bandit for reply style selection: grok vs curiosity vs standard.
    Used in reply_handler.py when intent >= 2.
    """
    global _reply_bandit
    if _reply_bandit is None:
        _reply_bandit = UCB1Bandit(
            namespace="reply_style",
            arms=["grok", "curiosity", "standard"],
            exploration_c=1.0,
            epsilon=0.15,       # 15% exploration
        )
    return _reply_bandit


def get_phrase_bandit(phrases: List[str]) -> UCB1Bandit:
    """
    Bandit for search phrase selection.
    Re-created automatically if the phrase list changes (e.g. after learning cycle).
    """
    global _phrase_bandit, _phrase_bandit_arms
    current_set = frozenset(phrases)
    if _phrase_bandit is None or _phrase_bandit_arms != current_set:
        _phrase_bandit = UCB1Bandit(
            namespace="search_phrase",
            arms=phrases,
            exploration_c=1.5,  # slightly higher — phrase space benefits from broader exploration
            epsilon=0.20,       # 20% exploration
        )
        _phrase_bandit_arms = current_set
    return _phrase_bandit
