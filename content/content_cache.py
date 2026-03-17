"""
Smart reply caching system with semantic matching.
(Unchanged from original - well-designed)
"""

import hashlib
import sqlite3
from datetime import datetime, timedelta
from typing import Optional
from logger_setup import logger
from config import Config


class ReplyCache:
    def __init__(self, db_path: str = None, expiry_days: int = 30):
        self.db_path = db_path or Config.DATABASE_PATH
        self.expiry_days = expiry_days
        self._access_count = 0
        self._init_connection()
        self._init_cache_table()

    def _init_connection(self):
        try:
            self.conn = sqlite3.connect(
                self.db_path,
                detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES,
                check_same_thread=False,
            )
            self.conn.row_factory = sqlite3.Row
            self.cursor = self.conn.cursor()
        except Exception as e:
            logger.error(f"Failed to open cache database: {e}")
            raise

    def _init_cache_table(self) -> None:
        try:
            self.cursor.execute("""
                CREATE TABLE IF NOT EXISTS reply_cache (
                    id INTEGER PRIMARY KEY,
                    tweet_hash TEXT UNIQUE,
                    original_text TEXT,
                    generated_reply TEXT,
                    quality_score REAL,
                    created_at TIMESTAMP,
                    last_used TIMESTAMP,
                    usage_count INTEGER DEFAULT 1
                )
            """)
            self.cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_tweet_hash ON reply_cache(tweet_hash)
            """)
            self.conn.commit()
        except Exception as e:
            logger.error(f"Failed to initialize cache table: {e}")

    def _hash_tweet(self, text: str) -> str:
        return hashlib.md5(text.strip().lower().encode()).hexdigest()

    def _semantic_similarity(self, text1: str, text2: str) -> float:
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())
        if not words1 or not words2:
            return 0.0
        intersection = len(words1 & words2)
        union = len(words1 | words2)
        return intersection / union if union > 0 else 0.0

    def _cleanup_expired(self):
        try:
            cutoff = datetime.now() - timedelta(days=self.expiry_days)
            self.cursor.execute("DELETE FROM reply_cache WHERE created_at < ?", (cutoff.isoformat(),))
            deleted = self.cursor.rowcount
            if deleted:
                self.conn.commit()
                logger.debug(f"Cleaned up {deleted} expired cache entries")
        except Exception as e:
            logger.error(f"Expired cache cleanup failed: {e}")

    def get(self, tweet_text: str, similarity_threshold: float = 0.7) -> Optional[dict]:
        try:
            self._access_count += 1
            if self._access_count % 100 == 0:
                self._cleanup_expired()

            tweet_hash = self._hash_tweet(tweet_text)
            cutoff = datetime.now() - timedelta(days=self.expiry_days)

            self.cursor.execute(
                "SELECT generated_reply, quality_score, created_at FROM reply_cache WHERE tweet_hash = ?",
                (tweet_hash,)
            )
            row = self.cursor.fetchone()

            if row:
                created_at = row[2]
                if isinstance(created_at, str):
                    try:
                        created_at = datetime.fromisoformat(created_at)
                    except Exception:
                        created_at = datetime.min

                if created_at and created_at >= cutoff:
                    self.cursor.execute(
                        "UPDATE reply_cache SET last_used = ?, usage_count = usage_count + 1 WHERE tweet_hash = ?",
                        (datetime.now().isoformat(), tweet_hash)
                    )
                    self.conn.commit()
                    return {"reply": row[0], "quality_score": row[1] or 0.5, "source": "cache_exact"}

            self.cursor.execute(
                "SELECT tweet_hash, original_text, generated_reply, quality_score FROM reply_cache WHERE created_at > ? ORDER BY quality_score DESC LIMIT 50",
                (cutoff,)
            )
            for cached_hash, cached_text, cached_reply, cached_quality in self.cursor.fetchall():
                similarity = self._semantic_similarity(tweet_text, cached_text)
                if similarity >= similarity_threshold:
                    return {"reply": cached_reply, "quality_score": cached_quality or 0.5, "source": "cache_semantic"}

            return None
        except Exception as e:
            logger.error(f"Cache get failed: {e}")
            return None

    def is_duplicate_reply(self, reply: str, similarity_threshold: float = 0.9) -> bool:
        try:
            reply_hash = self._hash_tweet(reply)
            self.cursor.execute("SELECT 1 FROM reply_cache WHERE tweet_hash = ?", (reply_hash,))
            if self.cursor.fetchone():
                return True

            cutoff = datetime.now() - timedelta(days=self.expiry_days)
            self.cursor.execute(
                "SELECT generated_reply FROM reply_cache WHERE created_at > ? ORDER BY quality_score DESC LIMIT 100",
                (cutoff.isoformat(),)
            )
            for (cached_reply,) in self.cursor.fetchall():
                if self._semantic_similarity(reply, cached_reply) >= similarity_threshold:
                    return True
            return False
        except Exception as e:
            logger.error(f"Duplicate cache check failed: {e}")
            return False

    def set(self, tweet_text: str, reply: str, quality_score: float = 0.5) -> bool:
        try:
            tweet_hash = self._hash_tweet(tweet_text)
            now = datetime.now().isoformat()
            self.cursor.execute(
                "INSERT OR REPLACE INTO reply_cache (tweet_hash, original_text, generated_reply, quality_score, created_at, last_used, usage_count) VALUES (?, ?, ?, ?, ?, ?, 1)",
                (tweet_hash, tweet_text, reply, quality_score, now, now)
            )
            self.conn.commit()
            return True
        except Exception as e:
            logger.error(f"Cache set failed: {e}")
            return False

    def cleanup_old_entries(self, days: int = 30) -> int:
        try:
            cutoff_date = datetime.now() - timedelta(days=days)
            self.cursor.execute("DELETE FROM reply_cache WHERE created_at < ?", (cutoff_date.isoformat(),))
            deleted = self.cursor.rowcount
            self.conn.commit()
            return deleted
        except Exception as e:
            logger.error(f"Cache cleanup failed: {e}")
            return 0

    def get_stats(self) -> dict:
        try:
            self.cursor.execute("SELECT COUNT(*) FROM reply_cache")
            total = self.cursor.fetchone()[0]
            self.cursor.execute("SELECT SUM(usage_count) FROM reply_cache")
            total_uses = self.cursor.fetchone()[0] or 0
            self.cursor.execute("SELECT AVG(quality_score) FROM reply_cache")
            avg_quality = self.cursor.fetchone()[0] or 0
            return {
                "total_cached_replies": total,
                "total_uses": total_uses,
                "avg_quality_score": round(avg_quality, 2),
            }
        except Exception as e:
            logger.error(f"Failed to get cache stats: {e}")
            return {}
