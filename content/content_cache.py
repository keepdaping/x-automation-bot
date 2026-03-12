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


class ReplyCache:
    """Intelligent reply cache with semantic similarity matching."""

    def __init__(self, db_path: str = "data/bot.db"):
        """Initialize cache with database connection."""
        self.db_path = db_path
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

    def get(self, tweet_text: str, similarity_threshold: float = 0.7) -> Optional[str]:
        """
        Get cached reply for tweet, using exact and semantic matching.
        
        Args:
            tweet_text: The tweet to find a reply for
            similarity_threshold: Min similarity (0-1) for semantic matches
            
        Returns:
            Cached reply if found, None otherwise
        """
        try:
            tweet_hash = self._hash_tweet(tweet_text)
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Exact match (fastest)
            cursor.execute(
                "SELECT generated_reply FROM reply_cache WHERE tweet_hash = ?",
                (tweet_hash,)
            )
            result = cursor.fetchone()
            
            if result:
                # Update usage stats
                cursor.execute(
                    """UPDATE reply_cache 
                       SET last_used = ?, usage_count = usage_count + 1
                       WHERE tweet_hash = ?""",
                    (datetime.now(), tweet_hash)
                )
                conn.commit()
                conn.close()
                logger.debug(f"Cache hit (exact): {tweet_hash[:8]}")
                return result[0]
            
            # Semantic match (if recent cache exists)
            cursor.execute(
                """SELECT tweet_hash, original_text, generated_reply 
                   FROM reply_cache 
                   WHERE created_at > ?
                   ORDER BY quality_score DESC
                   LIMIT 50""",
                (datetime.now() - timedelta(days=7),)  # Only recent 7 days
            )
            
            for (cached_hash, cached_text, cached_reply) in cursor.fetchall():
                similarity = self._semantic_similarity(tweet_text, cached_text)
                
                if similarity >= similarity_threshold:
                    logger.debug(f"Cache hit (semantic): {similarity:.2f}")
                    conn.close()
                    return cached_reply
            
            conn.close()
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
        Store generated reply in cache.
        
        Args:
            tweet_text: Original tweet
            reply: Generated reply
            quality_score: Quality score (0-1) for ranking
            
        Returns:
            True if successful, False otherwise
        """
        try:
            tweet_hash = self._hash_tweet(tweet_text)
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute(
                """INSERT OR REPLACE INTO reply_cache 
                   (tweet_hash, original_text, generated_reply, quality_score, created_at, last_used, usage_count)
                   VALUES (?, ?, ?, ?, ?, ?, 1)""",
                (tweet_hash, tweet_text, reply, quality_score, datetime.now(), datetime.now())
            )
            
            conn.commit()
            conn.close()
            logger.debug(f"Cached reply: {tweet_hash[:8]}")
            return True
            
        except Exception as e:
            logger.error(f"Cache set failed: {e}")
            return False

    def cleanup_old_entries(self, days: int = 30) -> int:
        """
        Remove old cache entries.
        
        Args:
            days: Remove entries older than this many days
            
        Returns:
            Number of entries deleted
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cutoff_date = datetime.now() - timedelta(days=days)
            cursor.execute(
                "DELETE FROM reply_cache WHERE created_at < ?",
                (cutoff_date,)
            )
            
            deleted = cursor.rowcount
            conn.commit()
            conn.close()
            
            logger.info(f"Cleaned up {deleted} old cache entries")
            return deleted
            
        except Exception as e:
            logger.error(f"Cache cleanup failed: {e}")
            return 0

    def get_stats(self) -> dict:
        """Get cache statistics."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("SELECT COUNT(*) FROM reply_cache")
            total = cursor.fetchone()[0]
            
            cursor.execute("SELECT SUM(usage_count) FROM reply_cache")
            total_uses = cursor.fetchone()[0] or 0
            
            cursor.execute("SELECT AVG(quality_score) FROM reply_cache")
            avg_quality = cursor.fetchone()[0] or 0
            
            conn.close()
            
            return {
                "total_cached_replies": total,
                "total_uses": total_uses,
                "avg_quality_score": round(avg_quality, 2),
                "avg_uses_per_reply": round(total_uses / total, 2) if total > 0 else 0,
            }
            
        except Exception as e:
            logger.error(f"Failed to get cache stats: {e}")
            return {}
