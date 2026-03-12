from playwright.sync_api import sync_playwright
import time

# Launch browser with stealth mode to avoid X detection
with sync_playwright() as p:
    browser = p.chromium.launch(
        headless=False,
        args=[
            "--disable-blink-features=AutomationControlled",
            "--disable-dev-shm-usage",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-component-update",
            "--disable-extensions",
            "--disable-sync",
            "--disable-default-apps",
            "--disable-background-networking",
            "--disable-background-timer-throttling",
            "--disable-breakpad",
            "--disable-client-side-phishing-detection",
            "--disable-default-apps",
            "--disable-hang-monitor",
            "--disable-popup-blocking",
            "--disable-prompt-on-repost",
            "--disable-sync",
            "--enable-automation=false",
        ]
    )
    
    context = browser.new_context(
        # Spoof a real browser identity
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        viewport={"width": 1920, "height": 1080}
    )
    
    page = context.new_page()
    
    # Inject script to hide automation detection
    page.add_init_script("""
        Object.defineProperty(navigator, 'webdriver', {
            get: () => undefined,
        });
        window.chrome = {
            runtime: {}
        };
    """)
    
    print("Opening X login page...")
    page.goto("https://x.com/login", wait_until="networkidle")
    
    time.sleep(3)
    
    print("\n" + "="*70)
    print("INSTRUCTIONS:")
    print("="*70)
    print("\n1. A browser window has opened with the X login page")
    print("2. Enter your credentials and log in normally")
    print("3. If 2FA is required, complete it")
    print("4. Wait for the page to fully load (you should see the home feed)")
    print("5. Return to this terminal and press ENTER")
    print("6. The session will be saved automatically")
    print("\n" + "="*70 + "\n")
    
    # Wait for the user to complete login
    input("Press ENTER after you finish logging in and the page has fully loaded...")
    
    # Wait additional time for all cookies to be set
    time.sleep(5)
    
    # Check if we're logged in by looking for home feed indicators
    try:
        # Try to find common elements that appear after successful login
        is_logged_in = page.locator('[aria-label="Home"]').is_visible(timeout=2000) if page.locator('[aria-label="Home"]').count() > 0 else False
        
        if is_logged_in:
            print("\n✓ Detected successful login!")
        else:
            print("\n⚠ Could not confirm login status, but will save session anyway...")
            print("   If login failed, you may need to try again.")
    except:
        print("\n⚠ Could not verify login status, but will save session...")
    
    # Save the authenticated session
    try:
        context.storage_state(path="session.json")
        print("✓ Session saved successfully to session.json")
        print("\nYou can now run: python run_bot.py")
    except Exception as e:
        print(f"\n✗ Error saving session: {e}")
    
    browser.close()
