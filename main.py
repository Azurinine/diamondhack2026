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
    add_group,
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


# async def watchdog_loop(browser: Browser):
#     while True:
#         cur = await browser.get_current_tab()
#         # TODO: Check if the url is on the blacklist later
#         if cur.url == "https://google.com":
            
#     pass    


async def cli_interface(browser: Browser):
    while True:
        cmd = await asyncio.to_thread(input, "Pilot > ")
        if cmd == "exit":
            break

        parts = cmd.strip().split()
        if not parts:
            continue

        command = parts[0]

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
    )

    await browser.start()
    await browser.navigate_to("https://google.com")
    
    # Run Watchdog and CLI concurrently
    await asyncio.gather(
        # watchdog_loop(), TODO AFTER CLI IS WORKING
        cli_interface(browser)
    )

    await browser.stop()

if __name__ == "__main__":
    asyncio.run(main())
