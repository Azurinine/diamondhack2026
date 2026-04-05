import asyncio
import os
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
    get_urls_for_first_active_task,
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

LOGIN_INDICATORS = (
    "login", "signin", "sign-in", "sign_in", "sso", "shibboleth",
    "auth", "oauth", "accounts.google.com", "cas/login", "idp",
)

async def wait_for_logins_if_needed(browser: Browser):
    """Check all open pages for login redirects. If any are found, pause and
    ask the user to log in manually, then wait for them to press Enter."""
    await asyncio.sleep(2)  # let redirects settle

    pages = await browser.get_pages()
    login_pages = []
    for page in pages:
        try:
            url = await page.get_url()
            if any(ind in url.lower() for ind in LOGIN_INDICATORS):
                login_pages.append(url)
        except Exception:
            pass

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
        f"I have opened tabs for task '{context['task_name']}' (id={context['task_id']}) "
        f"associated with group(s): {group_names}. "
        "All tabs should now be logged in. Navigate each tab to its correct destination "
        "based on the task. Do NOT complete the tasks themselves."
    )

    await wait_for_logins_if_needed(browser)

    print("[Watchdog] Starting Agent intervention...")
    agent = Agent(
        task=task_prompt,
        browser=browser,
        llm=ChatBrowserUse(),
    )
    await agent.run()
    print("[Watchdog] Intervention complete. Sleeping for 5 minutes.")
    await asyncio.sleep(5) # Cooldown

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

                    # Fetch the first active task and its associated group URLs
                    context = await get_urls_for_first_active_task()
                    if context:
                        # 1. Manually open the tabs through the urls list
                        for u in context["urls"]:
                            print(f"[Watchdog] Opening {u}")
                            await browser.new_page(url=u)
                        # 2. Run the agent to ensure all tabs are on the correct page
                        await run_agent_intervention(browser, context)
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
    #await browser.navigate_to("https://www.google.com")  # Initial page``
    
    # Run Watchdog and CLI concurrently
    await asyncio.gather(
        watchdog_loop(browser),
        cli_interface(browser)
    )

    await browser.stop()

if __name__ == "__main__":
    asyncio.run(main())
