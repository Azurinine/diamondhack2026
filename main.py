import asyncio
import os
import subprocess
import pyautogui
# from browser_use import Browser
from urllib.parse import urlparse
from dotenv import load_dotenv
from browser_use import Agent, Browser, ChatBrowserUse
from google import genai


from database import (
    init_db,
    save_urls_to_group,
    add_group, get_group_context,
    check_blacklist,
    get_urls_for_all_active_tasks,
)
from notion_sync import sync_notion_to_db

load_dotenv()

# TODO: Check if url should be blocked (Gemini API)
async def check_blacklist(url: str) -> bool:
    client = genai.Client()
    response = client.models.generate_content(
        model="gemini-flash-latest",
        contents=f"Check if this domain would ever be detrimental to schoolwork, be more harsh when deciding detrimentalness: {url},respond with only 'Yes' or 'No'."
    )
    valid = response.text.strip().lower() == "yes"
    return valid

LOGIN_URL_INDICATORS = (
    "login", "signin", "sign-in", "sign_in", "sso", "shibboleth",
    "auth", "oauth", "accounts.google.com", "cas/login", "idp",
)
LOGIN_TITLE_INDICATORS = (
    "log in", "login", "sign in", "signin", "authenticate",
    "shibboleth", "sso", "ucsd", "password",
)

async def _page_needs_login(page) -> bool:
    """Return True if the page looks like a login page (checks URL and title)."""
    try:
        url = await page.get_url()
        if any(ind in url.lower() for ind in LOGIN_URL_INDICATORS):
            return True
        title = await page.get_title()
        if title and any(ind in title.lower() for ind in LOGIN_TITLE_INDICATORS):
            return True
    except Exception:
        pass
    return False

async def wait_for_logins_if_needed(browser: Browser):
    """Check all open pages for login redirects (by URL and page title).
    If any are found, pause and ask the user to log in manually."""
    await asyncio.sleep(2)  # let redirects settle

    pages = await browser.get_pages()
    login_pages = []
    for page in pages:
        if await _page_needs_login(page):
            try:
                login_pages.append(await page.get_url())
            except Exception:
                login_pages.append("<unknown>")

    if login_pages:
        print("\n[Watchdog] Login required on the following pages:")
        for u in login_pages:
            print(f"  {u}")
        print("[Watchdog] Please log in manually in Chrome, then press Enter here to continue...")
        await asyncio.to_thread(input, "")
        print("[Watchdog] Resuming agent...")


async def run_agent_intervention(browser: Browser, context: dict):
    """Runs the AI agent to navigate tabs to their correct destinations."""
    group_names = ", ".join(g["name"] for g in context["groups"])

    task_prompt = (
        f"MISSION: Act as an expert Chief of Staff preparing a focused deep-work environment for the task: '{context['task_name']}' (ID: {context['task_id']}) "
        f"associated with the group(s): {group_names}.\n\n"
        
        "RULES OF ENGAGEMENT:\n"
        "1. NO WEB SEARCHING: Only use the currently open tabs as your starting points.\n"
        "2. NO WORK: Never solve, submit, or modify the actual assignment.\n"
        "3. FORWARD ONLY: Never click 'Back' or re-evaluate a page you have already processed.\n\n"
        
        "EXECUTION PROTOCOL (For each initial tab):\n"
        "STEP 1 - LOCATE: If the current tab is a dashboard/homepage, navigate directly to the specific page for this exact task (e.g., the exact Canvas assignment page or GitHub repo). If already there, proceed to Step 2.\n"
        "STEP 2 - DISCOVER & SPAWN: Once on the specific task page, scan for highly valuable supporting materials. This is the critical step. Look for:\n"
        "   - Starter code or repositories.\n"
        "   - Specific PDF readings required for THIS task.\n"
        "   - Rubrics or submission guidelines.\n"
        "   For every valuable material found, extract its URL and open it in a NEW background tab. Do NOT navigate away from the main task page.\n"
        "STEP 3 - RESTRAINT: You may open up to 4 highly relevant supporting tabs per initial tab (can have less than 4). Crucially, DO NOT switch to or scan the new tabs you just created. They are for the user to read later.\n"
        "STEP 4 - ADVANCE: Close any intermediate tabs you no longer need, ensure the main task page remains open, and move to the next initial tab.\n\n"
        "When all initial tabs are processed and supporting materials are spawned in the background, STOP."
    )

    await wait_for_logins_if_needed(browser)

    async def on_step_end(agent: Agent):
        await wait_for_logins_if_needed(browser)

    print("[Watchdog] Starting Agent intervention...")
    agent = Agent(
        task=task_prompt,
        browser=browser,
        llm=ChatBrowserUse(),
    )
    await agent.run(max_steps=30, on_step_end=on_step_end)
    print("[Watchdog] Intervention complete. Sleeping for 5 minutes.")
    await asyncio.sleep(5) # Cooldown

async def create_tab_group_for_task(browser: Browser, task_name: str, num_new_tabs: int):
    """Select newly opened tabs and create a named Chrome tab group using Ctrl+Cmd+P."""
    if num_new_tabs == 0:
        return

    all_pages = await browser.get_pages()
    total_tabs = len(all_pages)
    first_new_idx = total_tabs - num_new_tabs  # 0-based index of first new tab

    # Activate Chrome
    subprocess.run(
        ['osascript', '-e', 'tell application "Google Chrome" to activate'],
        capture_output=True,
    )
    await asyncio.sleep(0.5)

    # Navigate to the first newly opened tab.
    # Chrome: Cmd+1…9 (1-indexed). Tabs beyond 8 use Cmd+9 then step back.
    tab_number = first_new_idx + 1  # 1-indexed
    if tab_number <= 8:
        pyautogui.hotkey('command', str(tab_number))
    else:
        # Go to last tab, then step left until we reach the first new tab
        pyautogui.hotkey('command', '9')
        steps_back = total_tabs - first_new_idx - 1
        for _ in range(steps_back):
            pyautogui.hotkey('command', 'shift', '[')
            await asyncio.sleep(0.05)

    await asyncio.sleep(0.4)

    # Extend selection to cover all new tabs (Ctrl+Shift+Tab = shift-select left in Chrome)
    for _ in range(num_new_tabs - 1):
        pyautogui.hotkey('command', 'shift', ']')  # shift-select next tab
        await asyncio.sleep(0.05)

    await asyncio.sleep(0.3)

    # Fire the tab group shortcut
    pyautogui.hotkey('ctrl', 'command', 'p')
    await asyncio.sleep(0.5)

    # Type the task name and confirm
    pyautogui.write(task_name, interval=0.05)
    await asyncio.sleep(0.1)
    pyautogui.press('return')
    await asyncio.sleep(0.3)

    print(f"[Watchdog] Created tab group: '{task_name}'")


async def watchdog_loop(browser: Browser):
    print("[Watchdog] Started monitoring...")
    while True:
        try:
            # Polling logic: Retrieve current URL
            pages = await browser.get_pages()
            if pages:
                current_page = pages[0]
                url = await current_page.get_url()

                # Trigger condition: URL contains "google.com" or "neetcode.io"
                if "google.com" in url:
                    print(f"[Watchdog] Trigger detected: {url}. Intervening!")

                    # Fetch all active tasks and their associated group URLs
                    tasks = await get_urls_for_all_active_tasks()
                    if tasks:
                        for task in tasks:
                            # 1. Record tab count before opening this task's tabs
                            pages_before = await browser.get_pages()
                            count_before = len(pages_before)

                            # 2. Open all tabs for this task
                            for u in task["urls"]:
                                print(f"[Watchdog] Opening {u} for task '{task['task_name']}'")
                                await browser.new_page(url=u)

                            # 3. Group the newly opened tabs under the task name
                            pages_after = await browser.get_pages()
                            num_new = len(pages_after) - count_before
                            await create_tab_group_for_task(browser, task["task_name"], num_new)

                            # 4. Run the agent to ensure all tabs are on the correct page
                            await run_agent_intervention(browser, task)
        except Exception as e:
            print(f"[Watchdog] Error in loop: {e}")

        await asyncio.sleep(5)

async def cli_interface(browser: Browser):
    while True:
        cmd = await asyncio.to_thread(input, "Pilot > ")
        if cmd == "exit":
            break

        parts = cmd.strip().split()
        if not parts:
            continue

        command = parts[0] 
        arg = parts[1] if len(parts) > 1 else ""

        if command == "save":
            tabs = await browser.get_tabs()
            urls = [tab.url for tab in tabs]
            await save_urls_to_group(arg, urls)
            print(f"Saved {len(urls)} tab(s) to group '{arg}'")

        if command == "group":
            if len(parts) >= 3 and parts[1] == "add":
                name = parts[2]
                description = " ".join(parts[3:]) if len(parts) > 3 else ""
                try:
                    group_id = await add_group(name, description)
                    print(f"Success! Added group '{name}' with ID {group_id}")
                except Exception as e:
                    print(f"Error adding group: {e}")
            else:
                context = await get_group_context(arg)
                if not context:
                    print(f"Group '{arg}' not found.")
                else:
                    print(f"\n=== Mission Brief: {context['name']} ===")
                    print(f"Description: {context['description']}")
                    print(f"URLs ({len(context['urls'])}):")
                    for u in context['urls']:
                        flag = " [BLACKLISTED]" if u['is_blacklisted'] else ""
                        print(f"  {u['url']}{flag}")
                    print(f"Active Tasks ({len(context['tasks'])}):")
                    for t in context['tasks']:
                        print(f"  - {t['name']} (due: {t['due_date'] or 'N/A'}) [{t['source']}]")

        elif command == "audit":
            try:
                pages = await browser.get_pages()
                if pages:
                    url = await pages[0].get_url()
                    is_blocked = await check_blacklist(url)
                    status = "BLACKLISTED" if is_blocked else "OK"
                    print(f"[Audit] {url} → {status}")
            except Exception as e:
                print(f"[Audit] Error: {e}")
                print("Usage: group add <name> [description...]")

        elif command == "save":
            arg = " ".join(parts[1:]) if len(parts) > 1 else ""
            if not arg:
                print("Usage: save <group>")
            else:
                tabs = await browser.get_tabs()
                urls = [tab.url for tab in tabs]
                print(urls)
                await save_urls_to_group(arg, urls)
                print(f"Saved {len(urls)} tab(s) to group '{arg}'")
        
        elif command == "notion-sync":
            if not arg:
                db_id = os.getenv("NOTION_DATABASE_ID", "")
                if not db_id:
                    print("Usage: notion-sync <database_id>  (or set NOTION_DATABASE_ID in .env)")
                else:
                    await sync_notion_to_db(db_id)
            else:
                await sync_notion_to_db(arg)
                
        else:
            print(f"Unknown command: {command}")
        
        

async def main():
    await init_db()

    browser = Browser.from_system_chrome(
        profile_directory=os.getenv("CHROME_PROFILE"),
        keep_alive=True,
    )

    await browser.start()
    await browser.navigate_to("https://www.google.com")  # Initial page``
    
    # Run Watchdog and CLI concurrently
    await asyncio.gather(
        watchdog_loop(browser),
        cli_interface(browser)
    )

    await browser.stop()

if __name__ == "__main__":
    asyncio.run(main())