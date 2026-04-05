import asyncio
import os

import _ensure_repo_root  # noqa: F401

from dotenv import load_dotenv
from database import get_group_context
from notion_sync import fetch_notion_tasks, sync_notion_to_db

load_dotenv()


async def main():
    database_id = os.getenv("NOTION_DATABASE_ID", "")
    if not database_id:
        print("ERROR: Set NOTION_DATABASE_ID in your .env file and try again.")
        print("  (Find it in your Notion to-do list URL — the long hex string before '?v=')")
        return

    print(f"Testing Notion sync with database: {database_id}\n")

    # 1. Fetch without writing to DB
    print("--- Step 1: Fetch tasks from Notion ---")
    grouped = await fetch_notion_tasks(database_id)
    if not grouped:
        print("No tasks returned. Check that the integration has access to the database.")
        return

    for group, tasks in grouped.items():
        print(f"  Group '{group}': {len(tasks)} task(s)")
        for t in tasks:
            print(f"    • {t['name']}  (due: {t['due_date'] or 'N/A'})")

    # 2. Sync into SQLite
    print("\n--- Step 2: Sync into local DB ---")
    await sync_notion_to_db(database_id)

    # 3. Verify tasks appear via get_group_context
    print("\n--- Step 3: Verify DB contents ---")
    for group_name in grouped:
        ctx = await get_group_context(group_name)
        if ctx:
            print(f"  Group '{group_name}': {len(ctx['tasks'])} active task(s) in DB")
        else:
            print(f"  Group '{group_name}': NOT FOUND in DB (unexpected)")

    print("\nAll done.")


if __name__ == "__main__":
    asyncio.run(main())
