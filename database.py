import aiosqlite
from google import genai
from dotenv import load_dotenv
from urllib.parse import urlparse

DB_PATH = "databases/pilot.db"

load_dotenv()

async def _connect():
    """Open a connection with foreign keys enabled and row factory set."""
    db = await aiosqlite.connect(DB_PATH)
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA foreign_keys = ON")
    return db


# ── Part 1: Init ──────────────────────────────────────────────────────────────

async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        with open("databases/schema.sql", "r") as f:
            await db.executescript(f.read())

        # Migration: Add domain column to URLs table if it doesn't exist
        try:
            cursor = await db.execute("PRAGMA table_info(URLs)")
            columns = [row[1] for row in await cursor.fetchall()]
            if "domain" not in columns:
                await db.execute("ALTER TABLE URLs ADD COLUMN domain TEXT")
                await db.commit()
            
            # Backfill domains for all existing URLs
            cursor = await db.execute("SELECT id, url FROM URLs WHERE domain IS NULL OR domain = ''")
            rows = await cursor.fetchall()
            for row in rows:
                url_id, url = row[0], row[1]
                try:
                    parsed_url = urlparse(url)
                    domain = parsed_url.netloc
                    if domain.startswith("www."):
                        domain = domain[4:]
                    await db.execute("UPDATE URLs SET domain = ? WHERE id = ?", (domain, url_id))
                except Exception:
                    pass
        except Exception as e:
            print(f"Migration error: {e}")

        await db.commit()


# ── Part 2: Group & Workspace ─────────────────────────────────────────────────


async def add_group(name, description="") -> int:
    db = await _connect()
    try:
        await db.execute(
            "INSERT OR IGNORE INTO Groups (name, description) VALUES (?, ?)",
            (name, description)
        )
        await db.commit()
        cursor = await db.execute("SELECT id FROM Groups WHERE name = ?", (name,))
        row = await cursor.fetchone()
        return row["id"]
    finally:
        await db.close()


async def get_all_groups() -> list:
    db = await _connect()
    try:
        cursor = await db.execute("SELECT id, name, description FROM Groups")
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]
    finally:
        await db.close()


async def get_group_context(group_name) -> dict:
    """Returns group description, linked URLs, and active tasks as a nested dict."""
    db = await _connect()
    try:
        # Group info
        cursor = await db.execute(
            "SELECT id, name, description FROM Groups WHERE name = ?", (group_name,)
        )
        group = await cursor.fetchone()
        if not group:
            return {}
        group = dict(group)

        # Linked URLs
        cursor = await db.execute("""
            SELECT u.url, u.is_blacklisted FROM URLs u
            JOIN Group_URLs gu ON u.id = gu.url_id
            WHERE gu.group_id = ?
        """, (group["id"],))
        urls = [dict(r) for r in await cursor.fetchall()]

        # Active tasks
        cursor = await db.execute("""
            SELECT t.id, t.name, t.due_date, t.source FROM Tasks t
            JOIN Task_Groups tg ON t.id = tg.task_id
            WHERE tg.group_id = ? AND t.is_active = 1
        """, (group["id"],))
        tasks = [dict(r) for r in await cursor.fetchall()]

        return {
            "id": group["id"],
            "name": group["name"],
            "description": group["description"],
            "urls": urls,
            "tasks": tasks,
        }
    finally:
        await db.close()


# ── Part 3: URL & Watchdog ────────────────────────────────────────────────────
# TODO: Check if url should be blocked (Gemini API)
async def blackout(url: str) -> bool:
    client =  genai.Client()
    response = await client.aio.models.generate_content(
        model="gemini-flash-latest",
        contents=f"Check if this domain is a social media site or a gaming site,respond with only 'Yes' or 'No': {url},"
    )
    if response.text:
        return "yes" in response.text.strip().lower()
    return False
    
async def check_blacklist(url) -> bool:
    """Returns True if the given URL matches any blacklisted pattern (prefix match) or domain match."""
    db = await _connect()
    try:
        # Extract domain from URL
        parsed = urlparse(url)
        domain = parsed.netloc
        if domain.startswith("www."):
            domain = domain[4:]

        # Query for matches by prefix or by exact domain
        cursor = await db.execute(
            """
            SELECT 1 FROM URLs 
            WHERE (? LIKE url || '%' OR (domain = ? AND domain != '')) 
            AND is_blacklisted = 1
            """,
            (url, domain)
        )
        row = await cursor.fetchone()
        return row is not None
    finally:
        await db.close()


async def save_urls_to_group(group_name, urls: list):
    """Insert URLs and link them to a group. Silently skips duplicates."""
    db = await _connect()
    try:
        cursor = await db.execute("SELECT id FROM Groups WHERE name = ?", (group_name,))
        group = await cursor.fetchone()
        if not group:
            return
        group_id = group["id"]

        for url in urls:
            # Extract domain from URL
            domain = ""
            try:
                parsed_url = urlparse(url)
                domain = parsed_url.netloc
                if domain.startswith("www."):
                    domain = domain[4:] # Remove www. prefix for cleaner grouping
            except Exception:
                pass

            # Check if URL exists
            cursor = await db.execute("SELECT id, domain FROM URLs WHERE url = ?", (url,))
            url_row = await cursor.fetchone()
            if not url_row:
                print(f"🔍 New URL detected: {url}. Checking with Gemini...")
                is_blacklisted = await blackout(url)
                # Save the new URL to the DB with domain and AI blacklist result
                await db.execute(
                    "INSERT INTO URLs (url, domain, is_blacklisted) VALUES (?, ?, ?)", 
                    (url, domain, 1 if is_blacklisted else 0)
                )
                # Get the ID of the row we just created
                cursor = await db.execute("SELECT id FROM URLs WHERE url = ?", (url,))
                url_row = await cursor.fetchone()
            else:
                print(f"✅ {url} found in local DB. Updating domain if needed.")
                # Backfill domain if it's currently empty
                if not url_row["domain"] or url_row["domain"] == "":
                    await db.execute("UPDATE URLs SET domain = ? WHERE id = ?", (domain, url_row["id"]))
            await db.execute(
                "INSERT OR IGNORE INTO Group_URLs (group_id, url_id) VALUES (?, ?)",
                (group_id, url_row["id"])
            )

        await db.commit()
    finally:
        await db.close()


async def remove_url_from_group(group_name: str, url: str) -> bool:
    """Removes a URL from a group's context. Returns True if successfully removed."""
    db = await _connect()
    try:
        cursor = await db.execute(
            """
            SELECT gu.group_id, gu.url_id 
            FROM Group_URLs gu
            JOIN Groups g ON g.id = gu.group_id
            JOIN URLs u ON u.id = gu.url_id
            WHERE g.name = ? AND u.url = ?
            """, (group_name, url)
        )
        link = await cursor.fetchone()
        
        if link:
            await db.execute(
                "DELETE FROM Group_URLs WHERE group_id = ? AND url_id = ?",
                (link["group_id"], link["url_id"])
            )
            await db.commit()
            return True
        return False
    finally:
        await db.close()


async def toggle_blacklist(url) -> bool:
    """Flips is_blacklisted for a URL. Returns the new value."""
    db = await _connect()
    try:
        await db.execute(
            "UPDATE URLs SET is_blacklisted = NOT is_blacklisted WHERE url = ?", (url,)
        )
        await db.commit()
        cursor = await db.execute("SELECT is_blacklisted FROM URLs WHERE url = ?", (url,))
        row = await cursor.fetchone()
        return bool(row["is_blacklisted"]) if row else False
    finally:
        await db.close()

async def blacklisted(url) -> bool:
    """Returns True if the specified URL is blacklisted."""
    db = await _connect()
    try:
        cursor = await db.execute("SELECT 1 FROM URLs WHERE url = ? AND is_blacklisted = 1", (url,))
        row = await cursor.fetchone()
        return row is not None
    finally:
        await db.close()

# ── Part 4: Task Endpoints ────────────────────────────────────────────────────

async def sync_tasks(group_name, tasks: list):
    """Wipe-and-replace: deactivate old tasks, insert new batch for the group."""
    db = await _connect()
    try:
        cursor = await db.execute("SELECT id FROM Groups WHERE name = ?", (group_name,))
        group = await cursor.fetchone()
        if not group:
            return
        group_id = group["id"]

        # Deactivate existing tasks for this group
        cursor = await db.execute(
            "SELECT task_id FROM Task_Groups WHERE group_id = ?", (group_id,)
        )
        task_ids = [r["task_id"] for r in await cursor.fetchall()]
        if task_ids:
            placeholders = ",".join("?" * len(task_ids))
            await db.execute(
                f"UPDATE Tasks SET is_active = 0 WHERE id IN ({placeholders})", task_ids
            )

        # Insert new tasks and link them
        for task in tasks:
            cursor = await db.execute(
                "INSERT INTO Tasks (name, due_date, source, is_active) VALUES (?, ?, ?, 1)",
                (task["name"], task.get("due_date"), task.get("source", "manual"))
            )
            task_id = cursor.lastrowid
            await db.execute(
                "INSERT OR IGNORE INTO Task_Groups (task_id, group_id) VALUES (?, ?)",
                (task_id, group_id)
            )

        await db.commit()
    finally:
        await db.close()


async def upsert_inferred_task(group_name, name, due_date=None) -> int:
    """Add an agent-inferred task (from Canvas/Gradescope) and link it to a group."""
    db = await _connect()
    try:
        cursor = await db.execute("SELECT id FROM Groups WHERE name = ?", (group_name,))
        group = await cursor.fetchone()
        if not group:
            return -1
        group_id = group["id"]

        await db.execute(
            "INSERT OR IGNORE INTO Tasks (name, due_date, source) VALUES (?, ?, 'inferred')",
            (name, due_date)
        )
        cursor = await db.execute("SELECT id FROM Tasks WHERE name = ? AND source = 'inferred'", (name,))
        task = await cursor.fetchone()
        task_id = task["id"]

        await db.execute(
            "INSERT OR IGNORE INTO Task_Groups (task_id, group_id) VALUES (?, ?)",
            (task_id, group_id)
        )
        await db.commit()
        return task_id
    finally:
        await db.close()


async def get_urls_for_first_active_task() -> dict | None:
    """Find the first active task (by id), resolve its groups and URLs."""
    db = await _connect()
    try:
        cursor = await db.execute(
            "SELECT id, name FROM Tasks WHERE is_active = 1 ORDER BY id ASC LIMIT 1"
        )
        task = await cursor.fetchone()
        if not task:
            return None
        task = dict(task)

        cursor = await db.execute("""
            SELECT g.id, g.name FROM Groups g
            JOIN Task_Groups tg ON g.id = tg.group_id
            WHERE tg.task_id = ?
        """, (task["id"],))
        groups = [dict(r) for r in await cursor.fetchall()]

        urls = []
        for group in groups:
            cursor = await db.execute("""
                SELECT u.url FROM URLs u
                JOIN Group_URLs gu ON u.id = gu.url_id
                WHERE gu.group_id = ? AND u.is_blacklisted = 0
            """, (group["id"],))
            urls.extend(row["url"] for row in await cursor.fetchall())

        return {
            "task_id": task["id"],
            "task_name": task["name"],
            "groups": groups,
            "urls": urls,
        }
    finally:
        await db.close()


# ── Legacy: kept for compatibility ───────────────────────────────────────────

async def get_group_urls(group_name) -> list:
    """Returns list of URL strings for a group."""
    db = await _connect()
    try:
        cursor = await db.execute("""
            SELECT u.url FROM URLs u
            JOIN Group_URLs gu ON u.id = gu.url_id
            JOIN Groups g ON g.id = gu.group_id
            WHERE g.name = ?
        """, (group_name,))
        rows = await cursor.fetchall()
        return [row["url"] for row in rows]
    finally:
        await db.close()
