"""
Smart reply caching system with semantic matching.
"""

import hashlib
import sqlite3
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

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
        """Initialize SQLite connection."""
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
        """Create cache table with reply_hash for duplicate prevention."""
        try:
            self.cursor.execute("""
                CREATE TABLE IF NOT EXISTS reply_cache (
                    id INTEGER PRIMARY KEY,
                    tweet_hash TEXT,
                    reply_hash TEXT UNIQUE,           -- Prevents near-duplicate replies
                    original_text TEXT,
                    generated_reply TEXT,
                    quality_score REAL,
                    created_at TIMESTAMP,
                    last_used TIMESTAMP,
                    usage_count INTEGER DEFAULT 1,
                    generation_type TEXT DEFAULT 'reply'  -- 'reply' or 'daily_tweet'
                )
            """)
            self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_tweet_hash ON reply_cache(tweet_hash)")
            self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_reply_hash ON reply_cache(reply_hash)")
            self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_created_at ON reply_cache(created_at)")
            self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_generation_type ON reply_cache(generation_type)")
            self.conn.commit()
        except Exception as e:
            logger.error(f"Failed to initialize cache table: {e}")

    def _hash_text(self, text: str) -> str:
        """MD5 hash for exact matching."""
        return hashlib.md5(text.strip().lower().encode()).hexdigest()

    def _semantic_similarity(self, text1: str, text2: str) -> float:
        """Jaccard similarity between two texts (used only for replies)."""
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())
        if not words1 or not words2:
            return 0.0
        intersection = len(words1 & words2)
        union = len(words1 | words2)
        return intersection / union if union > 0 else 0.0

    def _cleanup_expired(self):
        """Delete entries older than expiry_days."""
        try:
            cutoff = datetime.now() - timedelta(days=self.expiry_days)
            self.cursor.execute("DELETE FROM reply_cache WHERE created_at < ?", (cutoff,))
            deleted = self.cursor.rowcount
            if deleted > 0:
                self.conn.commit()
                logger.info(f"Cleaned up {deleted} expired cache entries")
        except Exception as e:
            logger.error(f"Expired cache cleanup failed: {e}")

    def get(self, tweet_text: str, generation_type: str = "reply", similarity_threshold: float = 0.80) -> Optional[Dict[str, Any]]:
        """
        Get cached reply.
        
        Args:
            tweet_text: Input tweet or seed text
            generation_type: 'reply' or 'daily_tweet'
            similarity_threshold: Jaccard threshold for semantic match (only used for 'reply')
        
        Returns: dict with reply info or None
        """
        try:
            self._access_count += 1
            if self._access_count % 30 == 0:  # Cleanup more frequently
                self._cleanup_expired()

            text_hash = self._hash_text(tweet_text)
            cutoff = datetime.now() - timedelta(days=self.expiry_days)

            # Step 1: Exact match (used for both reply and daily_tweet)
            self.cursor.execute(
                "SELECT generated_reply, quality_score, created_at, reply_hash "
                "FROM reply_cache WHERE tweet_hash = ? AND generation_type = ? AND created_at > ?",
                (text_hash, generation_type, cutoff)
            )
            row = self.cursor.fetchone()

            if row:
                reply, quality, created_at, reply_hash = row
                # Update usage stats
                self.cursor.execute(
                    "UPDATE reply_cache SET last_used = ?, usage_count = usage_count + 1 "
                    "WHERE reply_hash = ?",
                    (datetime.now().isoformat(), reply_hash)
                )
                self.conn.commit()
                logger.debug(f"Cache hit (exact): {generation_type} - quality {quality:.2f}")
                return {
                    "reply": reply,
                    "quality_score": quality or 0.5,
                    "source": "cache_exact",
                    "reply_hash": reply_hash
                }

            # Step 2: Semantic match — ONLY for replies (daily tweets skip this to ensure freshness)
            if generation_type == "reply":
                self.cursor.execute(
                    "SELECT original_text, generated_reply, quality_score, reply_hash "
                    "FROM reply_cache WHERE created_at > ? AND generation_type = 'reply' "
                    "ORDER BY quality_score DESC LIMIT 80",
                    (cutoff,)
                )
                for cached in self.cursor.fetchall():
                    cached_text = cached["original_text"]
                    similarity = self._semantic_similarity(tweet_text, cached_text)
                    if similarity >= similarity_threshold:
                        logger.debug(f"Cache hit (semantic): similarity {similarity:.2f}, quality {cached['quality_score']:.2f}")
                        return {
                            "reply": cached["generated_reply"],
                            "quality_score": cached["quality_score"] or 0.5,
                            "source": "cache_semantic",
                            "reply_hash": cached["reply_hash"]
                        }

            logger.debug(f"Cache miss: {generation_type} - {tweet_text[:60]}...")
            return None

        except Exception as e:
            logger.error(f"Cache get failed: {e}")
            return None

    def is_duplicate_reply(self, reply: str, similarity_threshold: float = 0.88) -> bool:
        """Check if this reply (or very similar) already exists."""
        try:
            reply_hash = self._hash_text(reply)
            self.cursor.execute("SELECT 1 FROM reply_cache WHERE reply_hash = ?", (reply_hash,))
            if self.cursor.fetchone():
                logger.debug(f"Duplicate reply detected (exact hash): {reply[:60]}...")
                return True

            # Semantic duplicate check (stricter threshold)
            cutoff = datetime.now() - timedelta(days=self.expiry_days)
            self.cursor.execute(
                "SELECT generated_reply FROM reply_cache WHERE created_at > ? LIMIT 150",
                (cutoff,)
            )
            for (cached_reply,) in self.cursor.fetchall():
                if self._semantic_similarity(reply, cached_reply) >= similarity_threshold:
                    logger.debug(f"Duplicate reply detected (semantic {self._semantic_similarity(reply, cached_reply):.2f}): {reply[:60]}...")
                    return True

            return False

        except Exception as e:
            logger.error(f"Duplicate reply check failed: {e}")
            return False

    def set(self, tweet_text: str, reply: str, quality_score: float = 0.5, generation_type: str = "reply") -> bool:
        """Cache a new reply — only if quality is good enough."""
        try:
            if quality_score < 0.65:
                logger.debug(f"Skipping cache — quality too low ({quality_score:.2f}): {reply[:60]}...")
                return False

            tweet_hash = self._hash_text(tweet_text)
            reply_hash = self._hash_text(reply)
            now = datetime.now().isoformat()

            self.cursor.execute(
                "INSERT OR REPLACE INTO reply_cache "
                "(tweet_hash, reply_hash, original_text, generated_reply, quality_score, "
                "created_at, last_used, usage_count, generation_type) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?)",
                (tweet_hash, reply_hash, tweet_text, reply, quality_score, now, now, generation_type)
            )
            self.conn.commit()
            logger.debug(f"Cached {generation_type} (quality {quality_score:.2f}): {reply[:60]}...")
            return True

        except Exception as e:
            logger.error(f"Cache set failed: {e}")
            return False

    def cleanup_old_entries(self, days: int = None) -> int:
        """Manually clean up expired entries."""
        days = days or self.expiry_days
        try:
            cutoff = datetime.now() - timedelta(days=days)
            self.cursor.execute("DELETE FROM reply_cache WHERE created_at < ?", (cutoff,))
            deleted = self.cursor.rowcount
            if deleted > 0:
                self.conn.commit()
                logger.info(f"Cleaned up {deleted} expired cache entries")
            return deleted
        except Exception as e:
            logger.error(f"Cache cleanup failed: {e}")
            return 0

    def get_stats(self) -> dict:
        """Get cache statistics."""
        try:
            self.cursor.execute("SELECT COUNT(*) FROM reply_cache")
            total = self.cursor.fetchone()[0]

            self.cursor.execute("SELECT COUNT(*) FROM reply_cache WHERE generation_type = 'reply'")
            reply_count = self.cursor.fetchone()[0]

            self.cursor.execute("SELECT COUNT(*) FROM reply_cache WHERE generation_type = 'daily_tweet'")
            daily_count = self.cursor.fetchone()[0]

            self.cursor.execute("SELECT SUM(usage_count) FROM reply_cache")
            total_uses = self.cursor.fetchone()[0] or 0

            self.cursor.execute("SELECT AVG(quality_score) FROM reply_cache")
            avg_quality = self.cursor.fetchone()[0] or 0.0

            self.cursor.execute("SELECT AVG(julianday('now') - julianday(created_at)) FROM reply_cache")
            avg_age_days = self.cursor.fetchone()[0] or 0.0

            return {
                "total_cached_entries": total,
                "reply_cache_count": reply_count,
                "daily_tweet_cache_count": daily_count,
                "total_usage_count": total_uses,
                "avg_quality_score": round(avg_quality, 2),
                "avg_age_days": round(avg_age_days, 1),
            }
        except Exception as e:
            logger.error(f"Failed to get cache stats: {e}")
            return {}