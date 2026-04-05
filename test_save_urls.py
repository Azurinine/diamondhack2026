import asyncio
from dotenv import load_dotenv
#keep this in root repository so it can access the database module and .env file
# Import your database functions
# Ensure these match the actual filenames in your directory
from database import init_db, _connect,save_urls_to_group,blackout
load_dotenv()

async def verify_database_contents():
    """Helper to print the current state of the URLs table."""
    db = await _connect()
    try:
        print("\n--- Current URLs Table State ---")
        cursor = await db.execute("SELECT id, url, is_blacklisted FROM URLs")
        rows = await cursor.fetchall()
        for row in rows:
            status = "❌ BLOCKED" if row["is_blacklisted"] else "✅ SAFE"
            print(f"ID: {row['id']} | {status} | URL: {row['url']}")
        print("--------------------------------\n")
    finally:
        await db.close()

async def test_save():
    print("🚀 Starting Test: save_urls_to_group")
    await init_db()
    
    # 1. ENSURE THE GROUP EXISTS FIRST
    from database import add_group
    await add_group("Study Session", "Testing group") 

    # 2. Now run the save logic
    test_group = "Study Session"
    test_urls = [
        "https://stackoverflow.com",
        "https://www.tiktok.com",
        "https://en.wikipedia.org"
    ]

    print(f"Adding URLs to group '{test_group}'...")
    await save_urls_to_group(test_group, test_urls)

    # 3. Verify
    await verify_database_contents()

if __name__ == "__main__":
    try:
        asyncio.run(test_save())
    except Exception as e:
        print(f"Test failed with error: {e}")