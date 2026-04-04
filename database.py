import aiosqlite
import os

DB_PATH = "pilot.db"

async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        with open("schema.sql", "r") as f:
            await db.executescript(f.read())
        await db.commit()

async def add_group(name, description=""):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT OR IGNORE INTO Groups (name, description) VALUES (?, ?)", (name, description))
        await db.commit()

async def get_group_urls(group_name):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("""
            SELECT u.url FROM URLs u
            JOIN Group_URLs gu ON u.id = gu.url_id
            JOIN Groups g ON g.id = gu.group_id
            WHERE g.name = ?
        """, (group_name,))
        rows = await cursor.fetchall()
        return [row[0] for row in rows]
