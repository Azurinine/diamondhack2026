import asyncio
import os
import time
import shlex
from dotenv import load_dotenv
from browser_use import Agent, Browser, ChatBrowserUse
from urllib.parse import urlparse
import subprocess
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

override_event = asyncio.Event()
on_break_until = 0.0
DEMO_MODE = os.getenv("DEMO_MODE", "false").lower() == "true"

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

    if DEMO_MODE or (context["task_name"] == "CSE101 HW1" and "CSE 101" in group_names):
        # Specialized Demo Prompt for Presentation
        task_prompt = (
            "CHOREOGRAPHED DEMO PROTOCOL:\n"
            "You are setting up a workspace for the CSE 101 HW1 presentation. Perform these EXACT steps:\n\n"
            "FIRST CLOSE THE CURRENT TAB AND THEN OPEN THE FOLLOWING TABS IN THE BACKGROUND:"
            "1. OVERLEAF: Find the tab with 'overleaf.com/project'. Locate the project named 'CSE101 HW1' and click to open it. MAKE SURE NOT TO CLOSE IT\n"
            "2. CANVAS: Find the tab with 'canvas.ucsd.edu'. Navigate to the 'Syllabus' section for CSE 101, click on the 'Content Calendar' and open the most recent lecture link.\n"
            "3. Scroll through the lecture slides and find the most relevant information for the assignment based on the first unfinished problem in the homework."
            "3. GEMINI (NEW TAB): Open a new background tab to 'https://gemini.google.com/app'. Once loaded, type exactly this into the chat and SUBMIT it: 'I am starting my CSE 101 HW1. I will ask you questions but I don't want answers, only guidance and Socratic hints.'\n"
            "4. EXTRA RESOURCES: Open one final background tab to 'https://visualgo.net/en/sorting' as a supporting visualization tool for this assignment.\n\n"
            "DO NOT perform any other actions. STOP when these steps are complete."
        )
    else:
        task_prompt = (
            f"MISSION: Act as an expert Chief of Staff preparing a focused deep-work environment for the task: '{context['task_name']}' (ID: {context['task_id']}) "
            f"associated with the group(s): {group_names}.\n\n"

            "RULES OF ENGAGEMENT:\n"
            "1. NO WEB SEARCHING: Only use the currently open tabs as your starting points.\n"
            "2. NO WORK: Never solve, submit, or modify the actual assignment.\n"
            "3. FORWARD ONLY: Never click 'Back' or re-evaluate a page you have already processed.\n"                                           
            "4. BLACKLIST CHECK: Before performing STEP 2 on any tab, call is_url_blacklisted with that tab's current URL. "                    
            "If it returns True, the site is blacklisted — skip STEP 2 entirely, do NOT close this tab, do NOT search this tab for tasks, and move immediately to the next tab.\n\n"  

            "EXECUTION PROTOCOL (For each initial tab):\n"
            "STEP 1 - LOCATE: If the current tab is a dashboard/homepage, navigate directly to the specific page for this exact task (e.g., the exact Canvas assignment page or GitHub repo). If already there, proceed to Step 2.\n"
            "STEP 2 - DISCOVER & SPAWN: Once on the specific task page, scan for highly valuable supporting materials. This is the critical step. Look for:\n"
            "   - Starter code or repositories.\n"
            "   - Specific PDF readings required for THIS task.\n"
            "   - Rubrics or submission guidelines.\n"
            "   For every valuable material found, extract its URL and open it in a NEW background tab. Do NOT navigate away from the main task page.\n"
            "STEP 3 - RESTRAINT: You may open up to 4 (max 4, does not need to use all 4) highly relevant supporting tabs per initial tab (can have less than 4). Crucially, DO NOT switch to or scan the new tabs you just created. They are for the user to read later.\n"
            "STEP 4 - ADVANCE: Close any intermediate tabs you no longer need, ensure the main task page remains open, and do NOT delete the original blacklisted site \n\n"
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

async def manual_override(url: str):
    try:
        print(f"[Watchdog] Override signal received for: {url}")
        # 1. Update your database/list
        await toggle_blacklist(url)
        # 2. Trigger the event to stop the 60s sleep in watchdog_loop
        override_event.set()
        # 3. CRITICAL: Return something so JS knows we are done!
        return "OK"
    except Exception as e:
        print(f"[Watchdog] Override Error: {e}")
        return "Error"

async def ask_mac_override(url: str) -> bool:
    """Uses a native macOS AppleScript dialog to ask the user for an override."""
    try:
        # Extract just the domain for a cleaner popup
        try:
            display_url = urlparse(url).netloc
            if not display_url:
                display_url = url
        except Exception:
            display_url = url

        script = f'''
        tell application "Google Chrome"
            activate
            try
                set dialogResult to display dialog "Watchdog Alert: {display_url} is blacklisted.\\n\\nDo you need to override this for school work?" buttons {{"Cancel", "Override"}} default button "Cancel" with title "Deep Work Pilot" giving up after 60
                return button returned of dialogResult
            on error
                return "Cancel"
            end try
        end tell
        '''
        # Run osascript in a thread so it doesn't block the async loop
        result = await asyncio.to_thread(subprocess.run, ['osascript', '-e', script], capture_output=True, text=True)
        return "Override" in result.stdout
    except Exception as e:
        print(f"[Watchdog] macOS popup error: {e}")
        return False

async def show_productivity_banner(browser, url: str):
    page_obj = await browser.get_current_page()
    if not page_obj:
        return

    # Use getattr to safely find the raw Playwright page
    playwright_page = getattr(page_obj, 'page', page_obj)

    print(f"[Watchdog] Injected warning banner for: {url}")
    js_code = """
    () => {
        const BANNER_ID = 'watchdog-override-banner';
        if (document.getElementById(BANNER_ID)) return;

        const div = document.createElement('div');
        div.id = BANNER_ID;
        div.style.cssText = "position:fixed !important; top:0 !important; left:0 !important; width:100% !important; " +
                           "background:#d9534f !important; color:white !important; padding:15px !important; " +
                           "z-index:2147483647 !important; font-family:sans-serif !important; box-shadow:0 2px 10px rgba(0,0,0,0.5) !important; " +
                           "display:flex !important; align-items:center !important; justify-content:center !important;";

        const container = document.createElement('div');
        container.style.cssText = "display:flex; align-items:center; justify-content:center; width:100%; max-width:850px; margin:0 auto; gap:15px;";

        const icon = document.createElement('span');
        icon.style.fontSize = "22px";
        icon.textContent = "🛑";

        const text = document.createElement('span');
        text.style.fontSize = "16px";
        const b = document.createElement('b');
        b.textContent = "Watchdog: ";
        text.appendChild(b);
        text.appendChild(document.createTextNode("Blacklisted. Please respond to the popup dialog..."));

        container.appendChild(icon);
        container.appendChild(text);
        div.appendChild(container);
        document.body.appendChild(div);
    }
    """
    try:
        await playwright_page.evaluate(js_code)
    except Exception as e:
        print(f"[Watchdog] Popup Error: {e}")

async def remove_productivity_banner(browser):
    """Removes the red warning banner from the page."""
    try:
        page_obj = await browser.get_current_page()
        if not page_obj:
            return
        playwright_page = getattr(page_obj, 'page', page_obj)
        js_code = """
        () => {
            const banner = document.getElementById('watchdog-override-banner');
            if (banner) banner.remove();
        }
        """
        await playwright_page.evaluate(js_code)
    except Exception:
        pass

async def watchdog_loop(browser: Browser):
    global on_break_until
    print("[Watchdog] Started monitoring...")
    last_url = None
    while True:
        try:
            # Check if we are on a break
            if time.time() < on_break_until:
                remaining = int(on_break_until - time.time())
                if remaining % 60 == 0 and remaining > 0:
                    print(f"[Watchdog] On break... {remaining // 60}m remaining")
                await asyncio.sleep(1)
                continue
            elif on_break_until > 0:
                print("[Watchdog] Break is over! Resuming monitoring.")
                on_break_until = 0.0 # Reset
                
            # Polling logic: Retrieve current URL
            pages = await browser.get_pages()
            if pages:
                current_page = pages[0]
                url = await current_page.get_url()

                if url and url != last_url:
                    last_url = url
                    
                    is_productive = await check_productivity(url,browser)
                    if is_productive:
                        continue   
                    if not is_productive:
                        print(f"[Watchdog] Trigger detected: {url}. Intervening!")
    
                        # Reset the event just in case CLI override is used
                        override_event.clear()
    
                        # Inject the passive warning banner
                        await show_productivity_banner(browser, url)
    
                        print("[Watchdog] Waiting for macOS popup override (60s max)...")
                        # Run the native macOS popup. It blocks for up to 60s.
                        override_granted = await ask_mac_override(url)
                        
                        # Remove the passive banner once interaction is complete or timed out
                        await remove_productivity_banner(browser)
                        
                        # Also check if the CLI triggered an override while the popup was showing
                        if override_granted or override_event.is_set():
                            print("[Watchdog] Override received! Staying on page.")
                            await manual_override(url)
                            continue # Skip the intervention and go back to monitoring
                        
                        print("[Watchdog] No override detected. Proceeding to intervention.")
                        still_blacklisted = await check_blacklist(url)
                        if still_blacklisted and not override_granted:
                            context = await get_urls_for_first_active_task(DEMO_MODE)
                            if context:
                                # 1. Open all workspace tabs first
                                for u in context["urls"]:
                                    print(f"[Watchdog] Opening {u}")
                                    await browser.new_page(url=u)
                                
                                # 2. Run the agent intervention ONCE for the whole workspace
                                await run_agent_intervention(browser, context)
                        else:
                            print("[Watchdog] Manual override detected via DB! Aborting intervention.")
        except Exception as e:
            print(f"[Watchdog] Error in loop: {e}")

        await asyncio.sleep(1) # Fast poll for responsiveness


async def cli_interface(browser: Browser):
    while True:
        cmd = await asyncio.to_thread(input, "\033[34m\nWatchDog > \033[0m")
        if not cmd:
            continue
        if cmd.lower() == "exit":
            break

        try:
            parts = shlex.split(cmd)
        except ValueError as e:
            print(f"Error parsing command: {e}")
            continue
            
        if not parts:
            continue

        command = parts[0] 
        arg = parts[1] if len(parts) > 1 else ""

        if command == "save":
            # Handle 'save [group] <name> [count]'
            start_idx = 1
            if len(parts) > 1 and parts[1] == "group":
                start_idx = 2
            
            if len(parts) <= start_idx:
                print("Usage: save [group] <group_name> [count]")
                continue
            
            group_name = parts[start_idx]
            
            count = None
            if len(parts) > start_idx + 1:
                try:
                    count = int(parts[start_idx + 1])
                except ValueError:
                    print("Error: Count must be an integer.")
                    continue
            
            tabs = await browser.get_tabs()
            if count is not None and count > 0:
                # Save the last X tabs (most recent)
                tabs = tabs[-count:]
            
            urls = [tab.url for tab in tabs]
            await save_urls_to_group(group_name, urls)
            print(f"Saved {len(urls)} tab(s) to group '{group_name}'")

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
                # Use shlex-parsed argument (parts[1]) as group name
                group_name = parts[1]
                context = await get_group_context(group_name)
                if not context:
                    print(f"Group '{group_name}' not found.")
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
                print("Usage: url list [group] [--all] | url add <group> <url> | url remove <group> <index/url>")
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
            
            elif action == "add":
                if len(parts) < 4:
                    print("Usage: url add <group> <url>")
                    continue
                group_name = parts[2]
                url = parts[3]
                await save_urls_to_group(group_name, [url])
                print(f"Success! Added '{url}' to group '{group_name}'")
            
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

        elif command == "override":
            # If a URL is provided, use it. Otherwise, use the current page's URL.
            url_to_override = arg
            if not url_to_override:
                try:
                    pages = await browser.get_pages()
                    if pages:
                        url_to_override = await pages[0].get_url()
                except Exception as e:
                    print(f"Error getting current URL: {e}")
            
            if url_to_override:
                print(f"Forcefully overriding: {url_to_override}")
                await manual_override(url_to_override)
            else:
                print("Usage: override [url]")

        elif command == "break":
            global on_break_until
            try:
                minutes = float(arg) if arg else 5.0 # Default 5 mins
                on_break_until = time.time() + (minutes * 60)
                print(f"✅ Taking a break for {minutes} minutes. Watchdog paused.")
            except ValueError:
                print("Usage: break [minutes]")

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
    await browser.navigate_to("https://google.com")
    
    # Run Watchdog and CLI concurrently
    await asyncio.gather(
        watchdog_loop(browser),
        cli_interface(browser)
    )
    await browser.stop()

if __name__ == "__main__":
    asyncio.run(main())
