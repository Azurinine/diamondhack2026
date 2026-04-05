import asyncio
from database import (
    init_db,
    add_group,
    save_urls_to_group,
    sync_tasks,
    toggle_blacklist
)

async def seed():
    print("Initializing Database Schema...")
    await init_db()

    # 1. Add LeetCode Group
    print("Seeding 'LeetCode' group...")
    await add_group("LeetCode", "Data Structures & Algorithms practice")
    
    # Add URLs for LeetCode
    await save_urls_to_group("LeetCode", [
        "https://leetcode.com/problemset/all/",
        "https://neetcode.io/roadmap",
        "https://www.youtube.com/c/NeetCode"
    ])
    
    # Add tasks for LeetCode
    await sync_tasks("LeetCode", [
        {"name": "Solve NeetCode 150: Two Sum", "source": "neetcode.io"},
        {"name": "Complete NeetCode Roadmap: Arrays & Hashing", "source": "neetcode.io"}
    ])

    # 2. Add Research Group
    print("Seeding 'Research' group...")
    await add_group("Research", "Deep Work Pilot & Agentic Browser development")
    
    # Add URLs for Research
    await save_urls_to_group("Research", [
        "https://github.com/browser-use/browser-use",
        "https://ai.google.dev/gemini-api/docs",
        "https://python-docs.aiosqlite.com/"
    ])
    
    # Add tasks for Research
    await sync_tasks("Research", [
        {"name": "Implement Watchdog loop in main.py", "source": "GitHub"},
        {"name": "Review Browser-Use SDK Action decorators", "source": "Docs"}
    ])

    # 3. Add Blacklisted URLs
    print("Seeding Blacklisted URLs...")
    # First save them to the 'General' group so they exist in the DB
    await save_urls_to_group("General", [
        "https://www.youtube.com",
        "https://www.facebook.com",
        "https://www.instagram.com"
    ])
    # Then toggle their blacklist status to True
    # await toggle_blacklist("https://www.youtube.com")
    # await toggle_blacklist("https://www.facebook.com")
    # await toggle_blacklist("https://www.instagram.com")

    print("\nDatabase successfully seeded with dummy variables!")

if __name__ == "__main__":
    asyncio.run(seed())