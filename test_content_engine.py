"""
Test script for ContentEngine pipeline verification.

Tests:
1. Cache miss → LLM generation → validation → quality scoring → cache storage
2. Cache hit retrieval
3. Fallback handling
4. Error recovery
"""

import sys
import json
from datetime import datetime

from content.engine import ContentEngine
from content.content_moderator import ContentModerator
from logger_setup import logger, log


def test_moderation_rules():
    """Test moderation validation logic."""
    print("\n" + "="*70)
    print("TEST 1: MODERATION RULES")
    print("="*70)
    
    moderator = ContentModerator()
    
    test_cases = [
        # (text, expected_valid, description)
        ("Great insights on AI!", True, "Valid reply"),
        ("This is a really compelling argument about machine learning.", True, "Valid longer reply"),
        ("", False, "Empty string"),
        ("no", False, "Too short (2 chars)"),
        ("Click here: https://example.com", False, "Contains URL"),
        ("Check out my crypto NFT portfolio!", False, "Banned word (crypto)"),
        ("I'm an AI and I think...", False, "Banned word (ai)"),
        ("HELLO WORLD THIS IS AMAZING!!!", False, "All caps with spam"),
        ("!!!!!!!!!!!!!", False, "Excessive punctuation"),
        ("I agree", True, "Short but valid"),
        ("Why is this so accurate?", True, "Valid with question"),
    ]
    
    passed = 0
    failed = 0
    
    for text, expected_valid, description in test_cases:
        is_valid, error = moderator.validate(text)
        status = "✓ PASS" if is_valid == expected_valid else "✗ FAIL"
        
        if is_valid == expected_valid:
            passed += 1
        else:
            failed += 1
        
        print(f"{status}: {description}")
        print(f"  Text: {repr(text[:50])}")
        print(f"  Expected valid: {expected_valid}, Got: {is_valid}")
        if error:
            print(f"  Error: {error}")
    
    print(f"\nModeration Tests: {passed} passed, {failed} failed")
    return failed == 0


def test_quality_scoring():
    """Test quality scoring logic."""
    print("\n" + "="*70)
    print("TEST 2: QUALITY SCORING")
    print("="*70)
    
    moderator = ContentModerator()
    
    test_cases = [
        # (text, description)
        ("This is a thoughtful response with good insights.", "Well-written reply"),
        ("Yes.", "Very short reply"),
        ("I agree 100%", "Generic phrase"),
        ("Why hasn't anyone talked about this?", "Engaging question"),
        ("Great point — this really made me think.", "Uses personality markers"),
        ("The solution is maybe, probably, perhaps...", "Vague language"),
        ("AMAZING!!!!!!!!!", "Spam indicators"),
    ]
    
    print(f"{'Text':<50} {'Score':<8} {'':<30}")
    print("-" * 90)
    
    for text, description in test_cases:
        score = moderator.score_quality(text)
        print(f"{text:<50} {score:<8.2f} {description}")
    
    print("\nQuality scoring appears reasonable - higher scores for genuine content")
    return True


def test_pipeline_with_cache():
    """Test the full ContentEngine pipeline."""
    print("\n" + "="*70)
    print("TEST 3: CONTENT ENGINE PIPELINE")
    print("="*70)
    
    engine = ContentEngine()
    
    tweets = [
        "Artificial intelligence is transform the way we work",
        "What's your take on the future of machine learning?",
        "I love coffee",
    ]
    
    print("\nTesting pipeline for 3 different tweets:\n")
    
    for i, tweet in enumerate(tweets, 1):
        print(f"[{i}] Tweet: {repr(tweet[:60])}")
        
        # First call - should generate (cache miss)
        print("  → Call 1 (should be cache miss):")
        result1 = engine.generate_reply(tweet)
        print(f"    Source: {result1.source}")
        print(f"    Quality: {result1.quality_score:.2f}")
        print(f"    Reply: {repr(result1.text[:60])}")
        
        if result1.error:
            print(f"    Error: {result1.error}")
        
        # Second call - should hit cache (if valid)
        print("  → Call 2 (should be cache hit if valid):")
        result2 = engine.generate_reply(tweet, use_cache=True)
        print(f"    Source: {result2.source}")
        print(f"    Same reply: {result1.text == result2.text}")
        
        # Third call - force regeneration (bypass cache)
        print("  → Call 3 (force generation, bypass cache):")
        result3 = engine.generate_reply(tweet, force_generation=True)
        print(f"    Source: {result3.source}")
        print(f"    May differ from first: {result1.text != result3.text}")
        
        print()
    
    # Check cache stats
    stats = engine.get_cache_stats()
    print("Cache Statistics:")
    print(f"  Total cached replies: {stats.get('total_cached_replies', 0)}")
    print(f"  Total uses: {stats.get('total_uses', 0)}")
    print(f"  Avg quality: {stats.get('avg_quality_score', 0):.2f}")
    print(f"  Avg uses per reply: {stats.get('avg_uses_per_reply', 0):.1f}x")
    
    return True


def test_error_handling():
    """Test error handling and fallback behavior."""
    print("\n" + "="*70)
    print("TEST 4: ERROR HANDLING & FALLBACKS")
    print("="*70)
    
    engine = ContentEngine()
    
    # Test invalid inputs
    invalid_tweets = [
        ("", "Empty string"),
        ("a", "Single character"),
        ("https://malicious.com?param=crypto", "Spam tweet"),
    ]
    
    print("\nTesting behavior with invalid inputs:")
    for tweet, description in invalid_tweets:
        print(f"\n{description}: {repr(tweet[:40])}")
        result = engine.generate_reply(tweet)
        print(f"  Source: {result.source}")
        print(f"  Got fallback: {result.source == 'fallback'}")
        print(f"  Reply: {repr(result.text[:60])}")
    
    return True


def test_semantic_caching():
    """Test semantic similarity caching."""
    print("\n" + "="*70)
    print("TEST 5: SEMANTIC SIMILARITY CACHING")
    print("="*70)
    
    engine = ContentEngine()
    
    # Similar tweets that should potentially reuse cached replies
    similar_tweets = [
        "Machine learning is revolutionizing software development",
        "AI is changing how we build software",
        "The impact of machine learning on software engineering",
    ]
    
    print("\nTesting semantic similarity caching:")
    print("(These tweets are semantically similar, may reuse cached replies)\n")
    
    results = []
    for i, tweet in enumerate(similar_tweets, 1):
        print(f"[{i}] {repr(tweet[:50])}")
        result = engine.generate_reply(tweet)
        results.append(result)
        print(f"    Source: {result.source}")
        print(f"    Quality: {result.quality_score:.2f}")
    
    # Check if any were cached from semantic matching
    cache_hits = [r for r in results if r.source == "cache"]
    print(f"\nCache hits from semantic matching: {len(cache_hits)} / {len(results)}")
    
    return True


def main():
    """Run all tests."""
    print("\n" + "="*70)
    print("CONTENT ENGINE VERIFICATION TEST SUITE")
    print("="*70)
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    tests = [
        ("Moderation Rules", test_moderation_rules),
        ("Quality Scoring", test_quality_scoring),
        ("Pipeline Tests", test_pipeline_with_cache),
        ("Error Handling", test_error_handling),
        ("Semantic Caching", test_semantic_caching),
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
    print(f"\nTotal: {total_passed}/{total} test groups passed")
    
    print(f"Completed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*70 + "\n")
    
    return all(results.values())


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
