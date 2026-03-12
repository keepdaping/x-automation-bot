"""
Debug script to verify session.json is valid and contains authentication cookies.
"""

import json
import os

def check_session():
    """Verify session.json exists and contains cookies."""
    
    print("="*70)
    print("SESSION.JSON VERIFICATION")
    print("="*70 + "\n")
    
    if not os.path.exists("session.json"):
        print("✗ session.json NOT FOUND")
        print("\nCreate it with:")
        print("  python import_cookies.py")
        return False
    
    try:
        with open("session.json", "r") as f:
            session = json.load(f)
        
        cookies = session.get("cookies", [])
        print(f"✓ session.json found")
        print(f"✓ Number of cookies: {len(cookies)}\n")
        
        # Check for important auth cookies
        cookie_names = [c["name"] for c in cookies]
        print("Cookies in session:")
        for name in cookie_names:
            print(f"  • {name}")
        
        important_cookies = ["auth_token", "ct0", "persisted_ids"]
        found_important = [c for c in important_cookies if c in cookie_names]
        
        if found_important:
            print(f"\n✓ Found important auth cookies: {', '.join(found_important)}")
        else:
            print("\n⚠ Warning: Did not find expected auth cookies")
            print("  Make sure you copied ALL cookies from Chrome")
        
        if len(cookies) > 0:
            print("\n✓ Session file looks valid!")
            print("\nYou can now run:")
            print("  python run_bot.py")
            return True
        else:
            print("\n✗ No cookies found in session.json")
            return False
    
    except json.JSONDecodeError as e:
        print(f"✗ session.json is invalid JSON: {e}")
        return False
    except Exception as e:
        print(f"✗ Error reading session.json: {e}")
        return False

if __name__ == "__main__":
    check_session()
