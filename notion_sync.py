import asyncio
import os
from dotenv import load_dotenv
from notion_client import AsyncClient
from database import init_db, add_group, sync_tasks

load_dotenv()

NOTION_API_KEY = os.getenv("NOTION_API_KEY")


def _extract_title(props: dict) -> str:
    for value in props.values():
        if value["type"] == "title":
            return "".join(t["plain_text"] for t in value["title"]).strip()
    return ""


def _extract_date(props: dict) -> str | None:
    for value in props.values():
        if value["type"] == "date" and value["date"]:
            return value["date"]["start"]
    return None


def _extract_group(props: dict) -> str | None:
    # Check well-known group property names first
    for key in ["Groups", "Group", "group", "Category", "category", "Course", "course", "Tag", "Tags"]:
        if key in props:
            prop = props[key]
            if prop["type"] == "select" and prop["select"]:
                return prop["select"]["name"]
            if prop["type"] == "multi_select" and prop["multi_select"]:
                return prop["multi_select"][0]["name"]
            if prop["type"] == "rich_text" and prop["rich_text"]:
                return "".join(t["plain_text"] for t in prop["rich_text"]).strip() or None

    # Fall back to any select/multi_select property
    for value in props.values():
        if value["type"] == "select" and value["select"]:
            return value["select"]["name"]
        if value["type"] == "multi_select" and value["multi_select"]:
            return value["multi_select"][0]["name"]

    return None


async def fetch_notion_tasks(database_id: str) -> dict[str, list]:
    """Query a Notion database and return tasks grouped by their group property.

    Returns a dict mapping group_name -> list of task dicts with keys:
    name, due_date, source.
    """
    notion = AsyncClient(auth=NOTION_API_KEY)

    # v3 API: get the data_source_id from the database's data_sources list
    db = await notion.databases.retrieve(database_id)
    data_sources = db.get("data_sources", [])
    if not data_sources:
        raise ValueError(f"No data sources found for database {database_id}")
    data_source_id = data_sources[0]["id"]

    results = []
    has_more = True
    start_cursor = None

    while has_more:
        kwargs: dict = {}
        if start_cursor:
            kwargs["start_cursor"] = start_cursor
        response = await notion.data_sources.query(data_source_id, **kwargs)
        results.extend(response.get("results", []))
        has_more = response.get("has_more", False)
        start_cursor = response.get("next_cursor")

    await notion.aclose()

    grouped: dict[str, list] = {}
    for page in results:
        props = page["properties"]
        name = _extract_title(props)
        if not name:
            continue
        due_date = _extract_date(props)
        group = _extract_group(props) or "General"

        grouped.setdefault(group, []).append({
            "name": name,
            "due_date": due_date,
            "source": "notion",
        })

    return grouped


async def sync_notion_to_db(database_id: str):
    """Fetch tasks from a Notion database and sync them into the local SQLite DB."""
    await init_db()

    print(f"Fetching tasks from Notion database: {database_id} ...")
    grouped = await fetch_notion_tasks(database_id)

    if not grouped:
        print("No tasks found in the Notion database.")
        return

    for group_name, tasks in grouped.items():
        print(f"  Syncing {len(tasks)} task(s) → group '{group_name}'")
        await add_group(group_name)
        await sync_tasks(group_name, tasks)

    total = sum(len(t) for t in grouped.values())
    print(f"Done. {total} task(s) synced across {len(grouped)} group(s).")


if __name__ == "__main__":
    import sys
    if len(sys.argv) != 2:
        print("Usage: python notion_sync.py <database_id>")
        sys.exit(1)
    asyncio.run(sync_notion_to_db(sys.argv[1]))
