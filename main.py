import asyncio
import os
from dotenv import load_dotenv
from browser_use import Agent, Browser, BrowserConfig
from database import init_db, get_group_urls

load_dotenv()

async def watchdog_loop():
    while True:
        print("[Watchdog] Auditing active tab...")
        # Logic to check active URL vs Blacklist goes here
        await asyncio.sleep(60)

async def cli_interface():
    while True:
        cmd = await asyncio.to_thread(input, "Pilot > ")
        if cmd == "exit":
            break
        print(f"Executing: {cmd}")

async def main():
    await init_db()
    
    # Run Watchdog and CLI concurrently
    await asyncio.gather(
        watchdog_loop(),
        cli_interface()
    )

if __name__ == "__main__":
    asyncio.run(main())
