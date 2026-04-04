import asyncio
import os
from dotenv import load_dotenv
# from browser_use import Agent, Browser, BrowserConfig
from database import (
    init_db, get_all_groups, get_group_context,
    save_urls_to_group, check_blacklist, toggle_blacklist,
    sync_tasks, upsert_inferred_task
)

load_dotenv()

# TODO: Uncomment this after CLI is working
# async def watchdog_loop():
#     while True:
#         print("[Watchdog] Auditing active tab...")
#         # Logic to check active URL vs Blacklist goes here
#         await asyncio.sleep(60)

async def cli_interface():
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
                # TODO: replace stub with real browser tab fetching
                stub_urls = ["https://stub.example.com"]
                await save_urls_to_group(arg, stub_urls)
                print(f"Saved {len(stub_urls)} tab(s) to group '{arg}'")

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
            # TODO: replace stub with real active tab URL from browser
            stub_url = "https://www.youtube.com/watch?v=stub"
            is_blocked = await check_blacklist(stub_url)
            status = "BLACKLISTED" if is_blocked else "OK"
            print(f"[Audit] {stub_url} → {status}")

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

        elif command:
            print(f"Unknown command: '{command}'. Try: save, mode, audit, break, exit")

async def main():
    await init_db()
    
    # Run Watchdog and CLI concurrently
    await asyncio.gather(
        # watchdog_loop(), TODO AFTER CLI IS WORKING
        cli_interface()
    )

if __name__ == "__main__":
    asyncio.run(main())
