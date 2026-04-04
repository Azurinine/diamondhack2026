import asyncio
import os
from dotenv import load_dotenv
from browser_use import Browser

load_dotenv()

async def test_browser():
    print("Initializing Browser Configuration...")
    
    # Load paths from your .env file
    chrome_path = os.getenv("CHROME_PATH")
    user_data = os.getenv("CHROME_USER_DATA")
    profile = os.getenv("CHROME_PROFILE")
    
    print(f"Chrome Path: {chrome_path}")
    print(f"User Data Dir: {user_data}")
    print(f"Profile Directory: {profile}")
    
    if not chrome_path or not user_data:
        print("Error: CHROME_PATH or CHROME_USER_DATA not found in .env file.")
        return

    print("Launching browser...")
    # Initialize the browser (API v0.12.6)
    browser = Browser(
        executable_path=chrome_path,
        user_data_dir=user_data,
        profile_directory=profile,
        headless=False,
    )
    
    try:
        # Start the browser session
        await browser.start()
        
        print("Navigating to google.com...")
        await browser.navigate_to("https://youtube.com")
        
        print("\nSUCCESS: Browser launched! Look for the Chrome window.")
        print("Press Ctrl+C in this terminal to close the connection and exit.")
        
        # Keep the script running indefinitely
        while True:
            await asyncio.sleep(1)
    except Exception as e:
        print(f"\nERROR: Could not launch browser. Ensure all Chrome windows are CLOSED.")
        print(f"Details: {e}")
        import traceback
        traceback.print_exc()
    finally:
        try:
            await browser.stop()
        except Exception:
            pass

if __name__ == "__main__":
    # Remember to completely close all existing Chrome windows before running!
    asyncio.run(test_browser())
