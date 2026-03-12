"""
X.COM SESSION CREATOR - COOKIE-BASED APPROACH
==============================================

This script creates session.json WITHOUT attempting to log in through Playwright.
Instead, it imports cookies from your real Chrome browser (where X accepts login).

X blocks Playwright login attempts but accepts cookie-based sessions!
"""

import json
from datetime import datetime, timezone
import re

print("="*70)
print("X.COM SESSION CREATOR - COOKIE IMPORT METHOD")
print("="*70)

print("""
IMPORTANT: X blocks automated login attempts, but accepts cookie-based sessions!

You have TWO options:

OPTION 1 (Recommended): Export cookies from your real Chrome browser
  1. Open Chrome (regular Chrome where you're logged into X)
  2. Go to x.com/home
  3. Press F12 → Application → Cookies → x.com
  4. Select ALL cookies (Ctrl+A)
  5. Copy them (Ctrl+C)
  6. Come back here and paste

OPTION 2: Use import_cookies.py script
  $ python import_cookies.py
  Then paste your cookies when prompted

Which option would you like?
""")

choice = input("Enter 1 or 2 (default 1): ").strip() or "1"

if choice == "1":
    print("\nOPTION 1: Paste cookies from Chrome")
    print("-" * 70)
    print("\nOpen your real Chrome browser right now:")
    print("  1. Make sure you're logged into X")
    print("  2. Press F12 and go to Application → Cookies → x.com")
    print("  3. Select ALL cookies (Ctrl+A)")
    print("  4. Copy (Ctrl+C)")
    print("  5. Come back and paste below")
    print("\nPaste your cookies (then press Enter twice):\n")
    
    lines = []
    empty_count = 0
    while empty_count < 2:
        try:
            line = input()
            if line.strip() == "":
                empty_count += 1
            else:
                empty_count = 0
                lines.append(line)
        except EOFError:
            break
    
    input_text = "\n".join(lines)
    
    if not input_text.strip():
        print("❌ No cookies pasted. Please try again.")
        exit(1)
    
    # Parse cookies from pasted data
    cookies = []
    
    print("\n✓ Parsing cookies...")
    
    for line in input_text.split('\n'):
        line = line.strip()
        if not line:
            continue
        
        # Split by tabs or multiple spaces
        parts = re.split(r'\t+|\s{2,}', line)
        
        if len(parts) >= 2:
            name = parts[0].strip()
            value = parts[1].strip()
            
            # Skip headers and empty
            if not name or name == 'Name' or name == 'Value':
                continue
            
            if name and value and len(value) > 3:
                cookie = {
                    "name": name,
                    "value": value,
                    "domain": "x.com",
                    "path": "/",
                    "expires": int(
                        (datetime.now(timezone.utc).timestamp() + (365 * 24 * 60 * 60))
                    ),
                    "httpOnly": False,
                    "secure": True,
                    "sameSite": "Lax"
                }
                cookies.append(cookie)
                print(f"  ✓ {name}")

elif choice == "2":
    print("\nOPTION 2: Using import_cookies.py script")
    print("-" * 70)
    print("Run this command instead:")
    print("  python import_cookies.py")
    print("\nThen paste your cookies when prompted.")
    exit(0)

else:
    print("Invalid choice. Please enter 1 or 2.")
    exit(1)

if not cookies:
    print("\n❌ No cookies parsed. Please check the format and try again.")
    exit(1)

# Create session.json
session = {
    "cookies": cookies,
    "origins": [
        {
            "origin": "https://x.com",
            "localStorage": []
        }
    ]
}

# Save to session.json
try:
    with open("session.json", "w") as f:
        json.dump(session, f, indent=2)
    
    print("\n" + "="*70)
    print("✅ SUCCESS!")
    print("="*70)
    print(f"\n✓ Created session.json with {len(cookies)} cookies")
    
    # Check for critical auth cookies
    cookie_names = [c["name"] for c in cookies]
    auth_cookies = [c for c in ["auth_token", "ct0", "att"] if c in cookie_names]
    
    if auth_cookies:
        print(f"✓ Found critical auth cookies: {', '.join(auth_cookies)}")
    else:
        print("⚠ WARNING: Missing expected auth cookies!")
        print("  Make sure you copied ALL cookies from Chrome DevTools")
    
    print("\nNext steps:")
    print("  1. Verify: python verify_session.py")
    print("  2. Run bot: python run_bot.py")
    print("="*70)

except Exception as e:
    print(f"\n❌ Error saving session.json: {e}")
    exit(1)

