"""
Engagement log writes and interaction outcome queries.
"""

import sqlite3
from logger_setup import log
from db.schema import DB_PATH


def log_engagement(action: str, target_id: str):
    conn = sqlite3.connect(DB_PATH)
    conn.execute("INSERT INTO engagement_log (action, target_id) VALUES (?, ?)", (action, target_id))
    conn.commit()
    conn.close()


def get_reply_outcomes(days: int = 7) -> list:
    """Returns success rates per intent + reply_style over the last N days."""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT intent, reply_style,
                   COUNT(*)              AS total,
                   SUM(got_reply_back)   AS replies,
                   SUM(got_follow)       AS follows,
                   SUM(got_dm)           AS dms,
                   AVG(outcome_score)    AS avg_score
            FROM interactions
            WHERE sent_at >= datetime('now', ?)
            GROUP BY intent, reply_style
            ORDER BY avg_score DESC
        """, (f"-{days} days",))
        return [
            {
                "intent": r[0],
                "reply_style": r[1],
                "total": r[2],
                "got_reply_back": r[3] or 0,
                "got_follow": r[4] or 0,
                "got_dm": r[5] or 0,
                "avg_outcome_score": round(r[6] or 0, 2),
            }
            for r in cur.fetchall()
        ]
    except Exception as e:
        log.warning(f"get_reply_outcomes failed: {e}")
        return []
    finally:
        conn.close()
