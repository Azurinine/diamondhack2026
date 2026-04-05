import asyncio
import os
from dotenv import load_dotenv
from browser_use import Agent, Browser, ChatBrowserUse
from google import genai


from database import (
    init_db,
    save_urls_to_group,
    add_group, 
    get_group_context,
    check_blacklist,
    get_all_groups,
    remove_url_from_group
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

async def watchdog_loop(browser: Browser):
    print("[Watchdog] Started monitoring...")
    last_url = None
    while True:
        try:
            # Polling logic: Retrieve current URL
            pages = await browser.get_pages()
            if pages:
                current_page = pages[0]
                url = await current_page.get_url()

                if url and url != last_url:
                    last_url = url
                    
                    # Trigger condition: URL contains "google.com"
                    if "google.com" in url:
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
                            print("[Watchdog] Intervention complete. Sleeping for 5 seconds.")
                            await asyncio.sleep(5) # Cooldown
        except Exception as e:
            print(f"[Watchdog] Error in loop: {e}")

        await asyncio.sleep(1) # Fast poll for responsiveness


async def cli_interface(browser: Browser):
    while True:
        cmd = await asyncio.to_thread(input, "\033[34mcoolThing > \033[0m")
        if not cmd:
            continue
        if cmd.lower() == "exit":
            break

        parts = cmd.strip().split()
        if not parts:
            continue

        command = parts[0] 
        arg = parts[1] if len(parts) > 1 else ""

        if command == "save":
            if not arg:
                print("Usage: save <group> [count]")
                continue
            
            count = None
            if len(parts) >= 3:
                try:
                    count = int(parts[2])
                except ValueError:
                    print("Error: Count must be an integer.")
                    continue
            
            tabs = await browser.get_tabs()
            if count is not None and count > 0:
                # Save the last X tabs (most recent)
                tabs = tabs[-count:]
            
            urls = [tab.url for tab in tabs]
            await save_urls_to_group(arg, urls)
            print(f"Saved {len(urls)} tab(s) to group '{arg}'")

        elif command == "group":
            if not arg or arg == "list":
                groups = await get_all_groups()
                print("\n=== Groups ===")
                for i, g in enumerate(groups, 1):
                    print(f"  {i}. {g['name']}: {g['description']}")
                    
            elif len(parts) >= 3 and parts[1] == "add":
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

        elif command == "url":
            if len(parts) < 2:
                print("Usage: url list [group] [--all] | url remove <group> <index/url>")
                continue
            
            action = parts[1]
            
            if action == "list":
                has_all = "--all" in parts
                # Extract group name if provided (ignoring --all)
                group_name = next((p for p in parts[2:] if p != "--all"), None)
                
                async def print_group_urls(g_name, show_full):
                    ctx = await get_group_context(g_name)
                    if not ctx:
                        print(f"Group '{g_name}' not found.")
                        return
                    print(f"\nURLs for {g_name}:")
                    urls = ctx.get('urls', [])
                    if not urls:
                        print("  (No URLs)")
                    for i, u in enumerate(urls, 1):
                        display_url = u['url']
                        if not show_full and len(display_url) > 60:
                            display_url = display_url[:57] + "..."
                        flag = " [BLACKLISTED]" if u['is_blacklisted'] else ""
                        print(f"  {i}. {display_url}{flag}")

                if group_name:
                    await print_group_urls(group_name, has_all)
                else:
                    groups = await get_all_groups()
                    for idx, g in enumerate(groups):
                        await print_group_urls(g['name'], has_all)
                        if idx < len(groups) - 1:
                            print("-" * 20)
            
            elif action == "remove":
                if len(parts) < 4:
                    print("Usage: url remove <group> <index/url>")
                    continue
                
                group_name = parts[2]
                target = parts[3]
                context = await get_group_context(group_name)
                if not context:
                    print(f"Group '{group_name}' not found.")
                    continue
                
                url_list = context.get('urls', [])
                url_to_remove = target
                
                try:
                    idx = int(target)
                    if 1 <= idx <= len(url_list):
                        url_to_remove = url_list[idx-1]['url']
                except ValueError:
                    pass

                success = await remove_url_from_group(group_name, url_to_remove)
                if success:
                    print(f"Successfully removed {url_to_remove}")
                    # Show updated list
                    new_context = await get_group_context(group_name)
                    print(f"\nUpdated URLs for {group_name}:")
                    for i, u in enumerate(new_context.get('urls', []), 1):
                        flag = " [BLACKLISTED]" if u['is_blacklisted'] else ""
                        print(f"  {i}. {u['url']}{flag}")
                else:
                    print(f"Error: Failed to remove {url_to_remove}.")
            else:
                print(f"Unknown url action: {action}")

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
    
    # Run Watchdog and CLI concurrently
    await asyncio.gather(
        watchdog_loop(browser),
        cli_interface(browser)
    )
    await browser.stop()

if __name__ == "__main__":
    asyncio.run(main())
