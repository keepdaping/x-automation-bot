from playwright.sync_api import sync_playwright
import time

print("="*70)
print("X.COM LOGIN SESSION CREATOR")
print("="*70)

# Simple, minimal browser launch - no stealth tricks that break the page
with sync_playwright() as p:
    # Minimal launch args to avoid blocking content
    browser = p.chromium.launch(
        headless=False,
        args=[
            "--start-maximized",
        ]
    )
    
    context = browser.new_context()
    page = context.new_page()
    
    print("\n[1/4] Opening X login page...")
    try:
        page.goto("https://x.com/login", wait_until="domcontentloaded", timeout=15000)
    except Exception as e:
        print(f"Warning: Page load timeout: {e}")
    
    time.sleep(2)
    
    print("[2/4] Page loaded. A browser window will open...")
    
    print("\n" + "="*70)
    print("MANUAL LOGIN REQUIRED:")
    print("="*70)
    print("\n✓ Browser window is in front of you")
    print("✓ You should see the X login page")
    print("\nSteps:")
    print("  1. Enter your Twitter/X credentials")
    print("  2. If prompted for 2FA, use your authenticator/SMS")
    print("  3. Wait for the page to load completely")
    print("  4. You should see your home feed")
    print("  5. Return to THIS terminal and press ENTER")
    print("\nNOTE: Do not close the browser window until you press ENTER here!")
    print("="*70 + "\n")
    
    # Wait for user to complete login
    input("⏳ Press ENTER when you've successfully logged in and page is fully loaded...")
    
    print("\n[3/4] Waiting for all cookies to be set...")
    time.sleep(3)
    
    print("[4/4] Saving session to session.json...")
    
    # Save the session
    try:
        context.storage_state(path="session.json")
        print("\n" + "="*70)
        print("✓ SUCCESS!")
        print("="*70)
        print("\n✓ Session saved successfully to session.json")
        print("\nYou can now run:")
        print("  python run_bot.py")
        print("\nThe bot will use your saved session automatically.")
        print("="*70 + "\n")
    except Exception as e:
        print(f"\n✗ ERROR saving session: {e}")
        print("\nPlease check:")
        print("  1. Did you actually log in?")
        print("  2. Is the page fully loaded?")
        print("  3. Try again with: python create_session.py")
    
    browser.close()
