"""
Smart reply caching system with semantic matching.

Stores generated replies and avoids regenerating for similar tweets
using both exact matching and semantic similarity.
"""

import hashlib
import sqlite3
from datetime import datetime, timedelta
from typing import Optional
import difflib

from logger_setup import logger
from config import Config


class ReplyCache:
    """Intelligent reply cache with semantic similarity matching.

    This class holds a persistent SQLite connection to avoid repeatedly
    opening the database.  Entries older than a configurable expiry are
    automatically deleted when `get()` is called.
    """

    def __init__(self, db_path: str = "data/bot.db"):
        """Initialize cache with database connection and ensure table exists."""
        self.db_path = db_path
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.cursor = self.conn.cursor()
        self._init_cache_table()

    def _init_cache_table(self) -> None:
        """Create reply_cache table if it doesn't exist."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
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
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_tweet_hash 
                ON reply_cache(tweet_hash)
            """)
            
            conn.commit()
            conn.close()
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

    def get(self, tweet_text: str, similarity_threshold: float = 0.7) -> Optional[tuple]:
        """
        Get cached reply for tweet, using exact and semantic matching.
        
        Returns tuple (reply, quality_score) or None.
        Entries older than Config.CACHE_EXPIRY_DAYS are cleaned up first.
        """
        try:
            # automatic expiry before lookup
            expiry = getattr(Config, "CACHE_EXPIRY_DAYS", 30)
            if expiry:
                cutoff = datetime.now() - timedelta(days=expiry)
                self.cursor.execute(
                    "DELETE FROM reply_cache WHERE created_at < ?",
                    (cutoff,)
                )
                self.conn.commit()

            tweet_hash = self._hash_tweet(tweet_text)
            
            # Exact match (fastest)
            self.cursor.execute(
                "SELECT generated_reply, quality_score FROM reply_cache WHERE tweet_hash = ?",
                (tweet_hash,)
            )
            result = self.cursor.fetchone()
            
            if result:
                reply, score = result
                # Update usage stats
                self.cursor.execute(
                    """UPDATE reply_cache 
                       SET last_used = ?, usage_count = usage_count + 1
                       WHERE tweet_hash = ?""",
                    (datetime.now(), tweet_hash)
                )
                self.conn.commit()
                logger.debug(f"Cache hit (exact): {tweet_hash[:8]}")
                return reply, score
            
            # Semantic match among recent entries
            cutoff_date = datetime.now() - timedelta(days=7)
            self.cursor.execute(
                """SELECT tweet_hash, original_text, generated_reply, quality_score
                   FROM reply_cache 
                   WHERE created_at > ?
                   ORDER BY quality_score DESC
                   LIMIT 50""",
                (cutoff_date,)
            )
            for cached_hash, cached_text, cached_reply, cached_score in self.cursor.fetchall():
                similarity = self._semantic_similarity(tweet_text, cached_text)
                if similarity >= similarity_threshold:
                    logger.debug(f"Cache hit (semantic): {similarity:.2f}")
                    return cached_reply, cached_score
            
            logger.debug(f"Cache miss: {tweet_hash[:8]}")
            return None
            
        except Exception as e:
            logger.error(f"Cache get failed: {e}")
            return None

    def set(
        self,
        tweet_text: str,
        reply: str,
        quality_score: float = 0.5
    ) -> bool:
        """
        Store generated reply in cache (or replace existing entry).
        """
        try:
            tweet_hash = self._hash_tweet(tweet_text)
            self.cursor.execute(
                """INSERT OR REPLACE INTO reply_cache 
                   (tweet_hash, original_text, generated_reply, quality_score, created_at, last_used, usage_count)
                   VALUES (?, ?, ?, ?, ?, ?, 1)""",
                (tweet_hash, tweet_text, reply, quality_score, datetime.now(), datetime.now())
            )
            self.conn.commit()
            logger.debug(f"Cached reply: {tweet_hash[:8]}")
            return True
            
        except Exception as e:
            logger.error(f"Cache set failed: {e}")
            return False

    def cleanup_old_entries(self, days: int = 30) -> int:
        """
        Remove old cache entries older than the given number of days.
        Operates on the persistent connection.
        """
        try:
            cutoff_date = datetime.now() - timedelta(days=days)
            self.cursor.execute(
                "DELETE FROM reply_cache WHERE created_at < ?",
                (cutoff_date,)
            )
            deleted = self.cursor.rowcount
            self.conn.commit()
            logger.info(f"Cleaned up {deleted} old cache entries")
            return deleted
        except Exception as e:
            logger.error(f"Cache cleanup failed: {e}")
            return 0

    def is_reply_similar(self, reply_text: str, threshold: float = 0.8) -> bool:
        """Determine if a reply similar to `reply_text` exists in cache.

        This method checks the most recent high-quality replies to avoid
        costly scans over the entire database.
        """
        try:
            cutoff_date = datetime.now() - timedelta(days=30)
            self.cursor.execute(
                "SELECT generated_reply FROM reply_cache "
                "WHERE created_at > ? ORDER BY quality_score DESC LIMIT 100",
                (cutoff_date,)
            )
            for (cached_reply,) in self.cursor.fetchall():
                if self._semantic_similarity(reply_text, cached_reply) >= threshold:
                    return True
            return False
        except Exception as e:
            logger.warning(f"Similarity check failed: {e}")
            return False

    def get_stats(self) -> dict:
        """Get cache statistics using the persistent cursor."""
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
