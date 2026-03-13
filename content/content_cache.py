"""
Smart reply caching system with semantic matching.

Stores generated replies and avoids regenerating for similar tweets
using both exact matching and semantic similarity.
"""

import hashlib
import sqlite3
from datetime import datetime, timedelta
from typing import Optional

from logger_setup import logger


class ReplyCache:
    """Intelligent reply cache with semantic similarity matching."""

    def __init__(self, db_path: str = "data/bot.db", expiry_days: int = 30):
        """Initialize cache with database connection."""
        self.db_path = db_path
        self.expiry_days = expiry_days
        self._access_count = 0
        self._init_connection()
        self._init_cache_table()

    def _init_connection(self):
        """Create a persistent SQLite connection used for all cache operations."""
        try:
            # Use a single connection to avoid repeated open/close overhead
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
        """Create reply_cache table if it doesn't exist."""
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
            
            # Create index on hash for fast lookups
            self.cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_tweet_hash 
                ON reply_cache(tweet_hash)
            """)
            
            self.conn.commit()
            logger.debug("Reply cache table initialized")
        except Exception as e:
            logger.error(f"Failed to initialize cache table: {e}")

    def _hash_tweet(self, text: str) -> str:
        """Create consistent hash of tweet text."""
        return hashlib.md5(text.strip().lower().encode()).hexdigest()

    def _semantic_similarity(self, text1: str, text2: str) -> float:
        """Calculate semantic similarity between two texts (0-1)."""
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())
        
        if not words1 or not words2:
            return 0.0
        
        intersection = len(words1 & words2)
        union = len(words1 | words2)
        
        return intersection / union if union > 0 else 0.0

    def _cleanup_expired(self):
        """Remove expired cache entries based on expiry_days."""
        try:
            cutoff = datetime.now() - timedelta(days=self.expiry_days)
            self.cursor.execute(
                "DELETE FROM reply_cache WHERE created_at < ?",
                (cutoff.isoformat(),)
            )
            deleted = self.cursor.rowcount
            if deleted:
                self.conn.commit()
                logger.debug(f"Cleaned up {deleted} expired cache entries")
        except Exception as e:
            logger.error(f"Expired cache cleanup failed: {e}")

    def get(self, tweet_text: str, similarity_threshold: float = 0.7) -> Optional[dict]:
        """Get cached reply for tweet, using exact and semantic matching.

        Args:
            tweet_text: The tweet to find a reply for
            similarity_threshold: Min similarity (0-1) for semantic matches

        Returns:
            Dict with keys: reply, quality_score, source ("exact"/"semantic")
            or None if no cache hit.
        """
        try:
            self._access_count += 1
            if self._access_count % 100 == 0:
                self._cleanup_expired()

            tweet_hash = self._hash_tweet(tweet_text)
            cutoff = datetime.now() - timedelta(days=self.expiry_days)

            # Exact match (fastest)
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
                        """UPDATE reply_cache 
                           SET last_used = ?, usage_count = usage_count + 1
                           WHERE tweet_hash = ?""",
                        (datetime.now().isoformat(), tweet_hash)
                    )
                    self.conn.commit()
                    logger.debug(f"Cache hit (exact): {tweet_hash[:8]}")
                    return {
                        "reply": row[0],
                        "quality_score": row[1] or 0.5,
                        "source": "cache_exact",
                    }

            # Semantic match
            self.cursor.execute(
                """SELECT tweet_hash, original_text, generated_reply, quality_score
                   FROM reply_cache
                   WHERE created_at > ?
                   ORDER BY quality_score DESC
                   LIMIT 50""",
                (cutoff,)
            )

            for cached_hash, cached_text, cached_reply, cached_quality in self.cursor.fetchall():
                similarity = self._semantic_similarity(tweet_text, cached_text)

                if similarity >= similarity_threshold:
                    logger.debug(f"Cache hit (semantic): {similarity:.2f}")
                    return {
                        "reply": cached_reply,
                        "quality_score": cached_quality or 0.5,
                        "source": "cache_semantic",
                    }

            logger.debug(f"Cache miss: {tweet_hash[:8]}")
            return None

        except Exception as e:
            logger.error(f"Cache get failed: {e}")
            return None

    def is_duplicate_reply(self, reply: str, similarity_threshold: float = 0.9) -> bool:
        """Check if a reply is already in cache (exact or near-duplicate)."""
        try:
            reply_hash = self._hash_tweet(reply)

            # Exact reply match
            self.cursor.execute(
                "SELECT 1 FROM reply_cache WHERE tweet_hash = ?",
                (reply_hash,)
            )
            if self.cursor.fetchone():
                return True

            # Near-duplicate match (use semantic similarity)
            cutoff = datetime.now() - timedelta(days=self.expiry_days)
            self.cursor.execute(
                """SELECT generated_reply FROM reply_cache 
                   WHERE created_at > ?
                   ORDER BY quality_score DESC
                   LIMIT 100""",
                (cutoff.isoformat(),)
            )

            for (cached_reply,) in self.cursor.fetchall():
                if self._semantic_similarity(reply, cached_reply) >= similarity_threshold:
                    return True

            return False

        except Exception as e:
            logger.error(f"Duplicate cache check failed: {e}")
            return False

    def set(
        self,
        tweet_text: str,
        reply: str,
        quality_score: float = 0.5
    ) -> bool:
        """Store generated reply in cache."""
        try:
            tweet_hash = self._hash_tweet(tweet_text)
            now = datetime.now().isoformat()

            self.cursor.execute(
                """INSERT OR REPLACE INTO reply_cache 
                   (tweet_hash, original_text, generated_reply, quality_score, created_at, last_used, usage_count)
                   VALUES (?, ?, ?, ?, ?, ?, 1)""",
                (tweet_hash, tweet_text, reply, quality_score, now, now)
            )

            self.conn.commit()
            logger.debug(f"Cached reply: {tweet_hash[:8]}")
            return True

        except Exception as e:
            logger.error(f"Cache set failed: {e}")
            return False

    def cleanup_old_entries(self, days: int = 30) -> int:
        """Remove old cache entries.

        Args:
            days: Remove entries older than this many days

        Returns:
            Number of entries deleted
        """
        try:
            cutoff_date = datetime.now() - timedelta(days=days)
            self.cursor.execute(
                "DELETE FROM reply_cache WHERE created_at < ?",
                (cutoff_date.isoformat(),)
            )
            deleted = self.cursor.rowcount
            self.conn.commit()
            logger.info(f"Cleaned up {deleted} old cache entries")
            return deleted

        except Exception as e:
            logger.error(f"Cache cleanup failed: {e}")
            return 0

    def get_stats(self) -> dict:
        """Get cache statistics."""
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
                "avg_uses_per_reply": round(total_uses / total, 2) if total > 0 else 0,
            }

        except Exception as e:
            logger.error(f"Failed to get cache stats: {e}")
            return {}
