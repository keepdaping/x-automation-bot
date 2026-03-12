#!/usr/bin/env python3
"""
Verify which Claude models are available in your Anthropic API account
"""

from anthropic import Anthropic
from config import Config
from logger_setup import log


def check_available_models():
    """Check which models are available"""
    if not Config.ANTHROPIC_API_KEY:
        print("❌ ANTHROPIC_API_KEY not set in .env")
        return
    
    # Debug: show first 20 chars of key
    api_key = Config.ANTHROPIC_API_KEY
    print(f"API Key loaded (first 20 chars): {api_key[:20]}...")
    
    client = Anthropic(api_key=api_key)
    
    # Test latest models - prioritize newer versions
    models_to_test = [
        # Latest Claude 3.5 models (2024)
        "claude-3-5-sonnet-20241022",
        "claude-3-5-haiku-20241022",
        # Claude 3.0 models (stable, widely available)
        "claude-3-opus-20240229",
        "claude-3-sonnet-20240229",
        "claude-3-haiku-20240307",
        # Older/newer attempts
        "claude-3-5-sonnet",
        "claude-3-haiku",
        "claude-3-opus",
    ]
    
    print("\n" + "=" * 70)
    print("TESTING CLAUDE MODELS")
    print("=" * 70 + "\n")
    
    available_models = []
    tested = 0
    
    for model in models_to_test:
        tested += 1
        try:
            # Try a simple message
            response = client.messages.create(
                model=model,
                max_tokens=10,
                messages=[
                    {"role": "user", "content": "hi"}
                ]
            )
            print(f"✅ {model:40} - AVAILABLE")
            available_models.append(model)
        except Exception as e:
            error_msg = str(e)
            if "not found" in error_msg.lower() or "not_found" in error_msg:
                print(f"❌ {model:40} - NOT FOUND")
            elif "invalid" in error_msg.lower() or "authentication" in error_msg.lower():
                print(f"⚠️  {model:40} - AUTH ERROR")
            elif "overloaded" in error_msg.lower():
                print(f"⚠️  {model:40} - API OVERLOADED (try again later)")
            else:
                short_error = error_msg.split('\n')[0][:40]
                print(f"⚠️  {model:40} - {short_error}")
    
    print("\n" + "=" * 70)
    print("RESULTS")
    print("=" * 70)
    
    if available_models:
        print(f"\n✅ Found {len(available_models)} working model(s)!\n")
        for model in available_models:
            print(f"  • {model}")
        
        print(f"\n📝 RECOMMENDED CONFIGURATION")
        print("-" * 70)
        fastest = available_models[0]
        print(f"""
Add to config.py:
  AI_MODEL_DRAFT = "{fastest}"
  AI_MODEL_CRITIQUE = "{fastest}"

Then run: python run_bot.py
        """)
    else:
        print(f"\n❌ No working models found!")
        print(f"\nTroubleshooting steps:")
        print(f"  1. Verify API key: https://console.anthropic.com/account/keys")
        print(f"  2. Check API key is not expired")
        print(f"  3. Check you have credits in your account")
        print(f"  4. Update .env with correct ANTHROPIC_API_KEY")
        print(f"  5. Try running this again in a few seconds")


if __name__ == "__main__":
    check_available_models()
