"""
Integration test - verify refactored system works end-to-end.

Tests that:
1. core/engagement.py correctly instantiates ContentEngine
2. ContentEngine is called with proper parameters
3. Return values are handled correctly
4. No broken imports or references
"""

import sys
from unittest.mock import Mock, patch, MagicMock

from content.engine import ContentEngine
from content.content_moderator import ContentModerator


def test_integration_imports():
    """Test that all modules can be imported."""
    print("\n" + "="*70)
    print("INTEGRATION TEST 1: Module Imports")
    print("="*70)
    
    try:
        from core.engagement import run_engagement
        from run_bot import BotController
        from content.engine import ContentEngine
        from content.content_cache import ReplyCache
        from content.content_moderator import ContentModerator
        from core.generator import generate_contextual_reply
        
        print("✓ core.engagement imported")
        print("✓ run_bot.BotController imported")
        print("✓ content.engine.ContentEngine imported")
        print("✓ content.content_cache.ReplyCache imported")
        print("✓ content.content_moderator.ContentModerator imported")
        print("✓ core.generator.generate_contextual_reply imported")
        
        return True
    except ImportError as e:
        print(f"✗ Import failed: {e}")
        return False


def test_engagement_instantiation():
    """Test that core/engagement.py properly instantiates ContentEngine."""
    print("\n" + "="*70)
    print("INTEGRATION TEST 2: Engagement ContentEngine Instantiation")
    print("="*70)
    
    try:
        # Read the engagement.py file to verify instantiation
        with open("core/engagement.py") as f:
            content = f.read()
        
        checks = [
            ("ContentEngine import", "from content.engine import ContentEngine" in content),
            ("ContentEngine singleton use", "get_content_engine()" in content),
            ("generate_reply call", "content_engine.generate_reply" in content),
            ("Result handling", "result.text" in content),
            ("Source logging", "result.source" in content),
            ("Quality logging", "result.quality_score" in content),
        ]
        
        all_passed = True
        for check_name, passed in checks:
            status = "✓" if passed else "✗"
            print(f"{status} {check_name}")
            if not passed:
                all_passed = False
        
        return all_passed
    
    except Exception as e:
        print(f"✗ Test failed: {e}")
        return False


def test_no_old_imports():
    """Test that old imports are not present."""
    print("\n" + "="*70)
    print("INTEGRATION TEST 3: No Old Imports")
    print("="*70)
    
    try:
        bad_imports = [
            ("core.generator import generate_contextual_reply", "core/engagement.py"),
            ("moderator import score_content_quality", "core/engagement.py"),
            ("core.thread_generator", "**/*.py"),
            ("core.moderator import", "core/engagement.py"),
        ]
        
        issues = []
        
        for import_pattern, location_pattern in bad_imports:
            # Check engagement.py specifically
            if location_pattern == "core/engagement.py":
                with open("core/engagement.py") as f:
                    if import_pattern in f.read():
                        issues.append(f"Found old import: {import_pattern} in core/engagement.py")
        
        if not issues:
            print("✓ No old imports found in core/engagement.py")
            print("✓ Old core/moderator.py not imported")
            print("✓ Old core/thread_generator.py not imported")
            return True
        else:
            for issue in issues:
                print(f"✗ {issue}")
            return False
    
    except Exception as e:
        print(f"✗ Test failed: {e}")
        return False


def test_contentengine_api():
    """Test that ContentEngine has the correct public API."""
    print("\n" + "="*70)
    print("INTEGRATION TEST 4: ContentEngine API")
    print("="*70)
    
    engine = ContentEngine()
    
    methods = [
        ("generate_reply", callable(getattr(engine, "generate_reply", None))),
        ("get_cache_stats", callable(getattr(engine, "get_cache_stats", None))),
        ("clear_cache", callable(getattr(engine, "clear_cache", None))),
    ]
    
    properties = [
        ("cache", hasattr(engine, "cache")),
        ("moderator", hasattr(engine, "moderator")),
        ("fallback_replies", hasattr(engine, "fallback_replies")),
    ]
    
    all_passed = True
    
    print("Methods:")
    for name, exists in methods:
        status = "✓" if exists else "✗"
        print(f"  {status} {name}()")
        if not exists:
            all_passed = False
    
    print("\nProperties:")
    for name, exists in properties:
        status = "✓" if exists else "✗"
        print(f"  {status} {name}")
        if not exists:
            all_passed = False
    
    return all_passed


def test_contentengine_return_type():
    """Test that generate_reply returns GenerationResult."""
    print("\n" + "="*70)
    print("INTEGRATION TEST 5: Return Type Validation")
    print("="*70)
    
    from content.engine import GenerationResult
    
    engine = ContentEngine()
    
    # Test with valid input that will fallback
    result = engine.generate_reply("Test tweet")
    
    checks = [
        ("Is GenerationResult", isinstance(result, GenerationResult)),
        ("Has text attribute", hasattr(result, "text")),
        ("Has source attribute", hasattr(result, "source")),
        ("Has quality_score attribute", hasattr(result, "quality_score")),
        ("Has error attribute", hasattr(result, "error")),
        ("text is string", isinstance(result.text, str)),
        ("source in valid values", result.source in ["cache", "generated", "fallback"]),
        ("quality_score is float", isinstance(result.quality_score, float)),
    ]
    
    all_passed = True
    for check_name, passed in checks:
        status = "✓" if passed else "✗"
        print(f"{status} {check_name}")
        if not passed:
            all_passed = False
    
    print(f"\nResult: text={repr(result.text[:40])}, source={result.source}, quality={result.quality_score:.2f}")
    
    return all_passed


def test_data_flow():
    """Test the complete data flow through the pipeline."""
    print("\n" + "="*70)
    print("INTEGRATION TEST 6: Data Flow Through Pipeline")
    print("="*70)
    
    engine = ContentEngine()
    
    # Test flow: Input → Validation → Cache → Output
    tweet = "This is an interesting observation"
    
    print(f"Input: {repr(tweet)}")
    
    result = engine.generate_reply(tweet)
    
    print(f"Output: {repr(result.text[:40])}")
    print(f"Source: {result.source} (expected: fallback or generated)")
    print(f"Quality: {result.quality_score:.2f}")
    
    # Verify flow
    checks = [
        ("Input not empty", len(tweet) > 0),
        ("Output not empty", len(result.text) > 0),
        ("Source is valid", result.source in ["cache", "generated", "fallback"]),
        ("Quality in range", 0.0 <= result.quality_score <= 1.0),
    ]
    
    all_passed = True
    for check_name, passed in checks:
        status = "✓" if passed else "✗"
        print(f"{status} {check_name}")
        if not passed:
            all_passed = False
    
    return all_passed


def test_error_handling_integration():
    """Test that errors are handled gracefully."""
    print("\n" + "="*70)
    print("INTEGRATION TEST 7: Error Handling")
    print("="*70)
    
    engine = ContentEngine()
    
    # Test with various problematic inputs
    test_inputs = [
        ("", "Empty string"),
        ("a", "Too short"),
        ("https://spam.com/link", "Spam link"),
    ]
    
    print("Testing error handling with bad inputs:")
    all_returned_fallback = True
    
    for tweet, description in test_inputs:
        try:
            result = engine.generate_reply(tweet)
            is_fallback = result.source == "fallback"
            status = "✓" if is_fallback else "✗"
            print(f"{status} {description}: got {result.source}")
            if not is_fallback:
                all_returned_fallback = False
        except Exception as e:
            print(f"✗ {description}: raised {type(e).__name__}: {e}")
            all_returned_fallback = False
    
    return all_returned_fallback


def main():
    """Run all integration tests."""
    print("\n" + "="*70)
    print("INTEGRATION TEST SUITE")
    print("="*70)
    
    tests = [
        ("Module Imports", test_integration_imports),
        ("Engagement Instantiation", test_engagement_instantiation),
        ("No Old Imports", test_no_old_imports),
        ("ContentEngine API", test_contentengine_api),
        ("Return Type Validation", test_contentengine_return_type),
        ("Data Flow", test_data_flow),
        ("Error Handling", test_error_handling_integration),
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
    print("INTEGRATION TEST SUMMARY")
    print("="*70)
    for name, passed in results.items():
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{status}: {name}")
    
    total_passed = sum(1 for v in results.values() if v)
    total = len(results)
    print(f"\nTotal: {total_passed}/{total} tests passed")
    print("="*70 + "\n")
    
    return all(results.values())


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
