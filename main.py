import asyncio
import os
from dotenv import load_dotenv
from browser_use import Agent, Browser, ChatBrowserUse, browser

from database import (
    init_db,
    save_urls_to_group,
    add_group, 
    get_group_context,
    check_blacklist,
    get_all_groups,
    remove_url_from_group,
    get_urls_for_first_active_task,toggle_blacklist
)
from notion_sync import sync_notion_to_db

load_dotenv()


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
        f"I have opened tabs for task '{context['task_name']}' (id={context['task_id']}) "
        f"associated with group(s): {group_names}. "
        "Do not search the web for anything. "
        "All tabs should now be logged in. For each tab, do the following ONCE and then stop:\n"
        "1. Navigate to the most specific page for the task (e.g. a specific assignment, "
        "problem set, repo, or document — not just a homepage). "
        "Use the CURRENT tab for this navigation — do NOT open a new tab just to navigate.\n"
        "2. Scan the page. Identify links that are at least 80% related to the task — "
        "include loosely related content such as hw1, homework 1, PDFs, rubrics, starter code, "
        "submission instructions, related readings, or anything a student would want open.\n"
        "3. Open each relevant link by right-clicking and opening in a new tab (or equivalent), "
        "so the current page stays open. NEVER navigate away from the current page to open a link — "
        "always open links in NEW tabs. Do NOT create intermediate navigation tabs.\n"
        "4. If you find no relevant content after one scan, close that tab and move on. "
        "Do NOT keep searching the same site.\n"
        "5. Once all starting tabs are processed, STOP. Do not re-scan or open links from the newly opened tabs.\n"
        "Do NOT complete, submit, or modify any tasks."
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

#TODO TO BE IMPLEMENTED
async def check_productivity(url: str,browser: Browser) -> bool:
    await save_urls_to_group("General", [url])
    is_blacklisted = await check_blacklist(url)
    
    # Initialize a default value
    productive = False 

    if is_blacklisted:
        print(f"[Watchdog] URL {url} is blacklisted. Checking for false positive...")
        productive = await productivity_agent(url, browser)
        
        if productive:
            print(f"[Watchdog] URL {url} is productive. Allowing access.")
            await toggle_blacklist(url) 
    else:
        # If it wasn't blacklisted to begin with, it's "productive" (allowed)
        productive = True
        
    return productive
async def productivity_agent(url: str,browser: Browser) -> bool:
    # 1. Define the structured XML prompt
    xml_task = f"""
<request>
    <context>Educational Content Filter</context>
    <data>
        <target_url>{url}</target_url>
    </data>
    <instructions>
        <task>Determine if the content of the target_url is educational or productive for schoolwork.</task>
        <logic>Return 'yes' for learning/research/tools; 'no' for entertainment/gaming/social media.</logic>
    </instructions>
    <constraints>
        <search>disabled</search>
        <source>internal_knowledge_only</source>
        <output_format>Return only the word 'yes' or 'no'.</output_format>
    </constraints>
</request>
""".strip()

    # 2. Pass the XML string as the task
    agent = Agent(
        task=xml_task,
        browser=browser,
        llm=ChatBrowserUse(),
    )
    # Since we are not searching, 1 step is enough for the LLM to process the string
    result = await agent.run(max_steps=1)
    
    # Extract the final result string from the agent's history/output
    # Note: Depending on your 'Agent' library, you might need result.final_answer() 
    # or just str(result). Here we assume the result is string-convertible.
    response_text = str(result).lower()
    
    print(f"[Productivity Agent] URL: {url} | Response: {response_text}")
    
    return "yes" in response_text


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
                    
                    # TODO IF URL IS BLACKLISTED THEN CALL FUNCTION CHECK PRODUCTIVITY (to be implemented)
                    is_productive = await check_productivity(url,browser)
                    if is_productive:
                        continue   
                    # Trigger condition: URL contains "google.com"
                    # TODO CHECK IF URL IN DATABASE IS BLACKLISTED, IF NOT FOUND THEN ADD URL
                    if not is_productive:
                        #delete url from database and add url to database with is_blacklisted = True
                        remove_url_from_group("General", url)
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
