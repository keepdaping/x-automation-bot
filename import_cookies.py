
"""
Script to import cookies from Chrome DevTools and create a Playwright session.json file.
"""

import json
from datetime import datetime, timezone
import re

def create_session_from_cookies():
    """Create a Playwright session.json from browser cookies."""
    
    print("="*70)
    print("X.COM COOKIE IMPORTER")
    print("="*70)
    print("\nPASTE COOKIES FROM CHROME DEVTOOLS:")
    print("  1. Open Chrome → F12 → Application → Cookies → x.com")
    print("  2. Select ALL cookies (Ctrl+A)")
    print("  3. Copy (Ctrl+C)")
    print("  4. Paste below and press Enter TWICE when done")
    print("="*70 + "\n")
    
    cookies = []
    lines = []
    
    print("(Paste the entire cookie table, then press Enter twice)")
    print("-" * 70)
    
    # Read multi-line input
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
        print("\n✗ No input received")
        return False
    
    # Parse the pasted data
    # Format: Name<TAB>Value<TAB>Domain<TAB>Path<TAB>Expires...
    
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
            
            # Skip header rows and empty names
            if not name or name == 'Name' or name == 'Value':
                continue
            
            # Only add valid cookie with name and value
            if name and value and len(value) > 3:  # Skip very short values
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
    
    if not cookies:
        print("\n✗ No cookies could be parsed")
        print("\nTroubleshooting:")
        print("  1. Make sure you copied from the COOKIES table (not headers)")
        print("  2. Select all cookies: Ctrl+A on the cookie table")
        print("  3. Copy: Ctrl+C")
        print("  4. Paste here")
        return False
    
    # Create session.json structure
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
        
        print(f"\nCritical auth cookies found: {', '.join(auth_cookies) if auth_cookies else '❌ MISSING'}")
        
        print("\nNext steps:")
        print("  1. Verify: python verify_session.py")
        print("  2. Run bot: python run_bot.py")
        print("="*70 + "\n")
        return True
    
    except Exception as e:
        print(f"\n✗ Error saving session.json: {e}")
        return False


if __name__ == "__main__":
    create_session_from_cookies()
