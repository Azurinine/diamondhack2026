"""
Tests tab group creation via Chrome's three-dot menu:
  ⋮ → Tab Groups → Create new tab group

Run: python tests/test_tab_group.py

Uses macOS System Events (accessibility API) to click Chrome's menu by name,
so it doesn't depend on window position or pixel coordinates.
"""
import asyncio
import os
import subprocess
import pyautogui
from dotenv import load_dotenv
from browser_use import Browser

load_dotenv()

GROUP_NAME = "TEST GROUP"
TEST_URLS  = ["https://www.wikipedia.org", "https://www.python.org"]


def run_applescript(script: str) -> tuple[str, str]:
    result = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
    return result.stdout.strip(), result.stderr.strip()


async def create_tab_group_via_menu(group_name: str):
    """
    Open Chrome's three-dot menu → Tab Groups → Create new tab group,
    then type the group name.
    Uses System Events accessibility API so no pixel coordinates are needed.
    """
    # Step 1: click the three-dot (⋮) button via accessibility
    script_click_menu = '''
    tell application "Google Chrome" to activate
    delay 0.4
    tell application "System Events"
        tell process "Google Chrome"
            -- The three-dot button's accessibility description
            click button "Customize and control Google Chrome" of toolbar 1 of window 1
        end tell
    end tell
    '''
    out, err = run_applescript(script_click_menu)
    if err:
        print(f"[menu] three-dot click error: {err}")
        return False
    print("[menu] opened three-dot menu")
    await asyncio.sleep(0.5)

    # Step 2: click "Tab Groups" in the dropdown
    script_tab_groups = '''
    tell application "System Events"
        tell process "Google Chrome"
            click menu item "Tab Groups" of menu 1 of button "Customize and control Google Chrome" of toolbar 1 of window 1
        end tell
    end tell
    '''
    out, err = run_applescript(script_tab_groups)
    if err:
        print(f"[menu] 'Tab Groups' click error: {err}")
        return False
    print("[menu] clicked 'Tab Groups'")
    await asyncio.sleep(0.4)

    # Step 3: click "Create new tab group" in the submenu
    script_create = '''
    tell application "System Events"
        tell process "Google Chrome"
            click menu item "Create new tab group" of menu 1 of menu item "Tab Groups" of menu 1 of button "Customize and control Google Chrome" of toolbar 1 of window 1
        end tell
    end tell
    '''
    out, err = run_applescript(script_create)
    if err:
        # Submenu may have already closed into a dialog/input — try arrow + enter fallback
        print(f"[menu] 'Create new tab group' error (trying keyboard fallback): {err}")
        pyautogui.press('return')
    else:
        print("[menu] clicked 'Create new tab group'")
    await asyncio.sleep(0.6)

    # Step 4: type the group name in whatever input Chrome opened
    print(f"[menu] typing group name: {group_name!r}")
    pyautogui.hotkey('command', 'a')
    pyautogui.write(group_name, interval=0.06)
    pyautogui.press('return')
    await asyncio.sleep(0.5)

    return True


async def main():
    browser = Browser.from_system_chrome(
        profile_directory=os.getenv("CHROME_PROFILE"),
        keep_alive=True,
    )
    await browser.start()

    print(f"Opening {len(TEST_URLS)} test tabs...")
    for url in TEST_URLS:
        await browser.new_page(url=url)
        await asyncio.sleep(0.6)

    print(f"\nAttempting to create tab group '{GROUP_NAME}' via three-dot menu...")
    success = await create_tab_group_via_menu(GROUP_NAME)

    if success:
        print(f"\nDone — check Chrome for a tab group named '{GROUP_NAME}'.")
    else:
        print("\nSomething went wrong — see errors above.")
        print("Tip: run the script below to list all accessibility button names in Chrome's toolbar:")
        print("""  osascript -e 'tell application "System Events" to tell process "Google Chrome" to get name of every button of toolbar 1 of window 1'""")


if __name__ == "__main__":
    asyncio.run(main())
