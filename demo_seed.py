import asyncio
from database import _connect

async def seed_demo():
    db = await _connect()
    try:
        print("Clearing old database entries...")
        await db.execute("DELETE FROM Group_URLs")
        await db.execute("DELETE FROM Task_Groups")
        await db.execute("DELETE FROM URLs")
        await db.execute("DELETE FROM Tasks")
        await db.execute("DELETE FROM Groups")

        print("Creating CSE 101 Group...")
        await db.execute("INSERT INTO Groups (name, description) VALUES (?, ?)", ("CSE 101", "Data Structures and Algorithms"))
        cursor = await db.execute("SELECT id FROM Groups WHERE name = 'CSE 101'")
        group_id = (await cursor.fetchone())["id"]

        print("Creating CSE101 HW1 Task...")
        await db.execute("INSERT INTO Tasks (name, due_date, source, is_active) VALUES (?, ?, ?, ?)", ("CSE101 HW1", "2026-04-10", "manual", 1))
        cursor = await db.execute("SELECT id FROM Tasks WHERE name = 'CSE101 HW1'")
        task_id = (await cursor.fetchone())["id"]

        print("Linking Task to Group...")
        await db.execute("INSERT INTO Task_Groups (task_id, group_id) VALUES (?, ?)", (task_id, group_id))

        print("Adding Canvas and Overleaf URLs...")
        # Gemini is removed from seed so the agent can "infer" it as an extra tab
        urls = [
            ("https://www.overleaf.com/project", "www.overleaf.com"),
            ("https://canvas.ucsd.edu/", "canvas.ucsd.edu")
        ]
        for url, domain in urls:
            await db.execute("INSERT INTO URLs (url, domain, is_blacklisted) VALUES (?, ?, 0)", (url, domain))
            cursor = await db.execute("SELECT id FROM URLs WHERE url = ?", (url,))
            url_id = (await cursor.fetchone())["id"]
            await db.execute("INSERT INTO Group_URLs (group_id, url_id) VALUES (?, ?)", (group_id, url_id))

        await db.commit()
        print("\n🎉 Demo Database Seeded Successfully!")
        print("====================================")
        print("Group: CSE 101")
        print("Task: CSE101 HW1 (Active)")
        print("URLs (Seed):")
        print("  - https://www.overleaf.com/project")
        print("  - https://canvas.ucsd.edu/")
        print("====================================")

    finally:
        await db.close()

if __name__ == "__main__":
    asyncio.run(seed_demo())
