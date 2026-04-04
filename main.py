import asyncio
import os
from browser_use import Browser, Agent, ChatBrowserUse
from dotenv import load_dotenv
from database import (
    init_db, get_all_groups, get_group_context,
    save_urls_to_group, check_blacklist, toggle_blacklist,
    sync_tasks, upsert_inferred_task
)
from notion_sync import sync_notion_to_db

load_dotenv()

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
                if "google.com" in url or "neetcode.io" in url:
                    print(f"[Watchdog] Trigger detected: {url}. Intervening!")

                    # Fetch the LeetCode group context
                    context = await get_group_context("LeetCode")
                    if context:
                        # 1. Manually open the tabs through the urls list
                        urls = [u["url"] for u in context.get("urls", [])]
                        for u in urls:
                            print(f"[Watchdog] Opening {u}")
                            await browser.new_page(url=u)

                        # 2. Run the agent to ensure all tabs are on the correct page
                        tasks = context.get("tasks", [])
                        task_names = "\n".join([f"- {t['name']}" for t in tasks])
                        task_prompt = (
                            "I have several tabs open for my 'LeetCode' workspace. "
                            "Please navigate these tabs to the correct problem pages based on the following tasks:\n"
                            f"{task_names}\n"
                            "For example, if a task is 'Two Sum', find the corresponding problem page on NeetCode and leave the tab open there. Do NOT solve the problems."
                        )

                        print("[Watchdog] Starting Agent intervention...")
                        agent = Agent(
                            task=task_prompt,
                            browser=browser,
                            llm=ChatBrowserUse(),
                        )
                        await agent.run()
                        print("[Watchdog] Intervention complete. Sleeping for 5 minutes.")
                        await asyncio.sleep(300) # Cooldown
        except Exception as e:
            print(f"[Watchdog] Error in loop: {e}")

        await asyncio.sleep(30)

async def cli_interface(browser: Browser):
    while True:
        cmd = await asyncio.to_thread(input, "Pilot > ")
        if cmd == "exit":
            break

        parts = cmd.strip().split(maxsplit=1)
        command = parts[0] if parts else ""
        arg = parts[1] if len(parts) > 1 else ""

        if command == "save":
            if not arg:
                print("Usage: save [group]")
            else:
                try:
                    tabs = await browser.get_tabs()
                    urls = [tab.url for tab in tabs]
                    await save_urls_to_group(arg, urls)
                    print(f"Saved {len(urls)} tab(s) to group '{arg}'")
                except Exception as e:
                    print(f"Error saving tabs: {e}")

        elif command == "mode":
            if not arg:
                groups = await get_all_groups()
                print("Available groups:")
                for g in groups:
                    print(f"  [{g['id']}] {g['name']} — {g['description']}")
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

        elif command == "break":
            mins = arg if arg else "5"
            print(f"[Break] Safe zone active for {mins} minute(s). Watchdog paused.")
            # TODO: integrate with watchdog_loop timer

        elif command == "blacklist":
            if not arg:
                print("Usage: blacklist [url]")
            else:
                new_val = await toggle_blacklist(arg)
                state = "blacklisted" if new_val else "removed from blacklist"
                print(f"'{arg}' is now {state}.")

        elif command == "notion-sync":
            if not arg:
                db_id = os.getenv("NOTION_DATABASE_ID", "")
                if not db_id:
                    print("Usage: notion-sync <database_id>  (or set NOTION_DATABASE_ID in .env)")
                else:
                    await sync_notion_to_db(db_id)
            else:
                await sync_notion_to_db(arg)

        elif command:
            print(f"Unknown command: '{command}'. Try: save, mode, audit, break, blacklist, notion-sync, exit")

async def main():
    await init_db()

    browser = Browser.from_system_chrome(
        profile_directory=os.getenv("CHROME_PROFILE"),
    )

    await browser.start()
    
    # Run Watchdog and CLI concurrently
    await asyncio.gather(
        watchdog_loop(browser),
        cli_interface(browser)
    )

    await browser.stop()

if __name__ == "__main__":
    asyncio.run(main())
