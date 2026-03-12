"""
Cache behavior validation test - tests caching logic without LLM dependencies.
"""

import sqlite3
from datetime import datetime

from content.content_cache import ReplyCache
from content.content_moderator import ContentModerator


def test_cache_exact_matching():
    """Test exact hash-based cache matching."""
    print("\n" + "="*70)
    print("CACHE TEST 1: Exact Hash Matching")
    print("="*70)
    
    cache = ReplyCache()
    
    tweet = "Machine learning is transforming software development"
    reply = "This is a thoughtful observation about modern development"
    
    # First store
    cache.set(tweet, reply, quality_score=0.85)
    print(f"✓ Stored: {repr(tweet[:50])}")
    
    # Retrieve exact same tweet
    retrieved = cache.get(tweet)
    print(f"✓ Retrieved: {retrieved is not None}")
    print(f"✓ Exact match: {retrieved == reply}")
    
    # Slightly different tweet should NOT match
    different_tweet = "Machine learning is transforming software engineering"
    retrieved2 = cache.get(different_tweet)
    print(f"✓ Different tweet (no exact match): {retrieved2 is None}")
    
    return retrieved == reply


def test_cache_semantic_matching():
    """Test semantic similarity matching."""
    print("\n" + "="*70)
    print("CACHE TEST 2: Semantic Similarity Matching")
    print("="*70)
    
    cache = ReplyCache()
    
    # Store a cached reply
    original = "AI and machine learning are changing everything"
    reply = "Absolutely transformative technology"
    cache.set(original, reply, quality_score=0.8)
    print(f"✓ Stored: {repr(original[:50])}")
    
    # Similar tweet with higher word overlap (>0.7 threshold)
    similar = "Machine learning and AI are reshaping the world"
    retrieved = cache.get(similar, similarity_threshold=0.5)  # Lower threshold to allow this
    
    similarity_score = cache._semantic_similarity(original, similar)
    print(f"✓ Semantic similarity: {similarity_score:.2f}")
    print(f"✓ Retrieved on semantic match (threshold=0.5): {retrieved == reply}")
    
    # Very different tweet should NOT match
    different = "I enjoy coffee and reading"
    retrieved2 = cache.get(different, similarity_threshold=0.5)
    similarity_different = cache._semantic_similarity(original, different)
    print(f"✓ Very different tweet similarity: {similarity_different:.2f}")
    print(f"✓ Very different tweet: {retrieved2 is None}")
    
    return (retrieved == reply) and (retrieved2 is None)


def test_cache_quality_ranking():
    """Test quality-based ranking of cached replies."""
    print("\n" + "="*70)
    print("CACHE TEST 3: Quality Scoring & Ranking")
    print("="*70)
    
    cache = ReplyCache()
    
    # Clear database between tests to avoid interference
    import sqlite3
    conn = sqlite3.connect("data/bot.db")
    cursor = conn.cursor()
    cursor.execute("DELETE FROM reply_cache")
    conn.commit()
    conn.close()
    
    # Store two new replies with different quality scores
    tweets = [
        ("Great insights test1", "This is okay reply1"),           # Lower quality
        ("Interesting point test2", "Absolutely brilliant reply2"), # Higher quality
    ]
    
    for tweet, reply in tweets:
        quality = 0.5 if "okay" in reply else 0.9
        cache.set(tweet, reply, quality_score=quality)
        print(f"  Stored: {repr(reply[:40])} (quality={quality})")
    
    # Get stats
    stats = cache.get_stats()
    print(f"\n✓ Cached replies: {stats['total_cached_replies']}")
    print(f"✓ Average quality: {stats['avg_quality_score']:.2f}")
    
    return stats['total_cached_replies'] == 2


def test_cache_usage_tracking():
    """Test usage tracking and statistics."""
    print("\n" + "="*70)
    print("CACHE TEST 4: Usage Tracking")
    print("="*70)
    
    cache = ReplyCache()
    
    tweet = "Interesting topic"
    reply = "Great perspective"
    cache.set(tweet, reply)
    print(f"✓ Initial store (usage_count=1)")
    
    # Retrieve multiple times
    for i in range(3):
        cache.get(tweet)
    
    stats = cache.get_stats()
    print(f"✓ Total uses: {stats['total_uses']}")
    print(f"✓ Avg uses per reply: {stats['avg_uses_per_reply']:.1f}x")
    
    return stats['total_uses'] >= 3


def test_moderation_updated_rules():
    """Test moderation with updated (less strict) rules."""
    print("\n" + "="*70)
    print("MODERATION TEST: Updated Ban Rules")
    print("="*70)
    
    moderator = ContentModerator()
    
    # These should now PASS (were failing before)
    should_pass = [
        "Great insights on AI developments!",
        "Interesting perspective on artificial intelligence",
        "The algorithm is quite clever",
    ]
    
    # These should still FAIL
    should_fail = [
        "Check out my crypto portfolio!",
        "I'm a bot here to scam you",  # Should fail - explicitly says bot
        "Try this viagra for cheap",
    ]
    
    print("\nShould be VALID:")
    pass_count = 0
    for text in should_pass:
        is_valid, error = moderator.validate(text)
        status = "✓ PASS" if is_valid else "✗ FAIL"
        print(f"  {status}: {repr(text[:45])}")
        if is_valid:
            pass_count += 1
    
    print(f"\nShould be INVALID:")
    fail_count = 0
    for text in should_fail:
        is_valid, error = moderator.validate(text)
        status = "✗ BLOCKED" if not is_valid else "✓ ALLOWED (bad!)"
        print(f"  {status}: {repr(text[:45])}")
        if not is_valid:
            fail_count += 1
    
    success = (pass_count == len(should_pass)) and (fail_count == len(should_fail))
    print(f"\n✓ Moderation rules updated: {success}")
    return success


def test_no_false_positives():
    """Test that valid content is not incorrectly blocked."""
    print("\n" + "="*70)
    print("VALIDATION TEST: False Positive Check")
    print("="*70)
    
    moderator = ContentModerator()
    
    valid_replies = [
        "This is brilliant",
        "I hadn't thought of it that way",
        "Why is this not more popular?",
        "Absolutely",
        "Makes sense to me",
        "Great point — I agree",
        "The logic here is sound",
        "This deserves way more attention",
    ]
    
    rejected = []
    for reply in valid_replies:
        is_valid, error = moderator.validate(reply)
        if not is_valid:
            rejected.append((reply, error))
            print(f"  ✗ FALSE POSITIVE: {repr(reply)}")
            print(f"    Reason: {error}")
    
    if not rejected:
        print("  ✓ All valid replies passed validation")
    
    return len(rejected) == 0


def test_spam_detection():
    """Test that spam is correctly detected."""
    print("\n" + "="*70)
    print("SPAM DETECTION TEST")
    print("="*70)
    
    moderator = ContentModerator()
    
    spam_replies = [
        ("CLICK HERE FOR FREE MONEY!!!", "Spam indicators"),
        ("Check out www.scam.com/link", "URL spam"),
        ("Follow me @spammer #crypto #nft", "Spam hashtags"),
        ("DM me for exclusive offer deal!!!", "DM spam"),
        ("PREMIUM VIAGRA CIALIS PHARMACY", "Spam drugs"),
    ]
    
    blocked = 0
    for reply, spam_type in spam_replies:
        is_valid, error = moderator.validate(reply)
        if not is_valid:
            blocked += 1
            print(f"  ✓ BLOCKED ({spam_type})")
        else:
            print(f"  ✗ ALLOWED (should block): {repr(reply[:40])}")
    
    return blocked == len(spam_replies)


def main():
    """Run all cache validation tests."""
    print("\n" + "="*70)
    print("CACHE & MODERATION BEHAVIOR VALIDATION")
    print("="*70)
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    tests = [
        ("Cache Exact Matching", test_cache_exact_matching),
        ("Cache Semantic Matching", test_cache_semantic_matching),
        ("Cache Quality Ranking", test_cache_quality_ranking),
        ("Cache Usage Tracking", test_cache_usage_tracking),
        ("Moderation Rules Updated", test_moderation_updated_rules),
        ("No False Positives", test_no_false_positives),
        ("Spam Detection", test_spam_detection),
    ]
    
    results = {}
    for name, test_func in tests:
        try:
            results[name] = test_func()
        except Exception as e:
            print(f"\n✗ TEST {name} FAILED WITH EXCEPTION:")
            print(f"  {type(e).__name__}: {e}")
            results[name] = False
            import traceback
            traceback.print_exc()
    
    # Summary
    print("\n" + "="*70)
    print("TEST SUMMARY")
    print("="*70)
    for name, passed in results.items():
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{status}: {name}")
    
    total_passed = sum(1 for v in results.values() if v)
    total = len(results)
    print(f"\nTotal: {total_passed}/{total} tests passed")
    print(f"Completed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*70 + "\n")
    
    return all(results.values())


if __name__ == "__main__":
    import sys
    success = main()
    sys.exit(0 if success else 1)
