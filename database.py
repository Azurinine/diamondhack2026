import aiosqlite

DB_PATH = "pilot.db"


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

async def check_blacklist(url) -> bool:
    """Returns True if the given URL matches any blacklisted pattern (prefix match)."""
    db = await _connect()
    try:
        cursor = await db.execute(
            "SELECT 1 FROM URLs WHERE ? LIKE url || '%' AND is_blacklisted = 1",
            (url,)
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
            await db.execute("INSERT OR IGNORE INTO URLs (url) VALUES (?)", (url,))
            cursor = await db.execute("SELECT id FROM URLs WHERE url = ?", (url,))
            url_row = await cursor.fetchone()
            await db.execute(
                "INSERT OR IGNORE INTO Group_URLs (group_id, url_id) VALUES (?, ?)",
                (group_id, url_row["id"])
            )

        await db.commit()
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
