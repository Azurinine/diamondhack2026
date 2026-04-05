"""
Quick backend tests — uses a temp DB so pilot.db is never touched.
Run with: python test_backend.py
"""
import asyncio
import os
import tempfile

import _ensure_repo_root  # noqa: F401

import database

# Point the module at a throwaway file for the duration of tests
_tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
database.DB_PATH = _tmp.name
_tmp.close()

PASS = "\033[32mPASS\033[0m"
FAIL = "\033[31mFAIL\033[0m"

def check(label, condition):
    print(f"  {'✓' if condition else '✗'} {label} ... {PASS if condition else FAIL}")
    if not condition:
        raise AssertionError(label)


async def run_tests():
    print("\n=== Deep Work Pilot — Backend Tests ===\n")

    # ── Part 1: Init ──────────────────────────────────────────────────────────
    print("[1] Schema init")
    await database.init_db()
    check("DB file created", os.path.exists(database.DB_PATH))

    # ── Part 2: Groups ────────────────────────────────────────────────────────
    print("\n[2] Groups")
    gid = await database.add_group("CSE 21", "Discrete math")
    check("add_group returns an int ID", isinstance(gid, int) and gid > 0)

    gid2 = await database.add_group("CSE 21", "Discrete math")
    check("add_group is idempotent (returns same ID)", gid == gid2)

    groups = await database.get_all_groups()
    names = [g["name"] for g in groups]
    check("get_all_groups includes seeded 'General'", "General" in names)
    check("get_all_groups includes 'CSE 21'", "CSE 21" in names)

    ctx = await database.get_group_context("CSE 21")
    check("get_group_context returns name", ctx["name"] == "CSE 21")
    check("get_group_context has urls list", isinstance(ctx["urls"], list))
    check("get_group_context has tasks list", isinstance(ctx["tasks"], list))

    empty = await database.get_group_context("nonexistent")
    check("get_group_context returns {} for unknown group", empty == {})

    # ── Part 3: URLs & Blacklist ──────────────────────────────────────────────
    print("\n[3] URLs & Blacklist")
    await database.save_urls_to_group("CSE 21", [
        "https://canvas.ucsd.edu/courses/cse21",
        "https://piazza.com/cse21",
    ])
    urls = await database.get_group_urls("CSE 21")
    check("save_urls_to_group stores 2 URLs", len(urls) == 2)

    await database.save_urls_to_group("CSE 21", ["https://canvas.ucsd.edu/courses/cse21"])
    urls = await database.get_group_urls("CSE 21")
    check("save_urls_to_group ignores duplicates", len(urls) == 2)

    await database.save_urls_to_group("General", ["https://youtube.com"])
    new_val = await database.toggle_blacklist("https://youtube.com")
    check("toggle_blacklist sets to True", new_val is True)

    new_val = await database.toggle_blacklist("https://youtube.com")
    check("toggle_blacklist toggles back to False", new_val is False)

    await database.toggle_blacklist("https://youtube.com")  # set blacklisted = True
    hit = await database.check_blacklist("https://youtube.com/watch?v=abc123")
    check("check_blacklist matches prefix (youtube.com/...)", hit is True)

    miss = await database.check_blacklist("https://canvas.ucsd.edu/courses/cse21")
    check("check_blacklist returns False for non-blacklisted URL", miss is False)

    # ── Part 4: Tasks ─────────────────────────────────────────────────────────
    print("\n[4] Tasks")
    await database.sync_tasks("CSE 21", [
        {"name": "HW 3", "due_date": "2026-04-10", "source": "manual"},
        {"name": "Midterm", "due_date": "2026-04-15", "source": "manual"},
    ])
    ctx = await database.get_group_context("CSE 21")
    check("sync_tasks inserts 2 active tasks", len(ctx["tasks"]) == 2)

    await database.sync_tasks("CSE 21", [
        {"name": "HW 4", "due_date": "2026-04-20", "source": "manual"},
    ])
    ctx = await database.get_group_context("CSE 21")
    task_names = [t["name"] for t in ctx["tasks"]]
    check("sync_tasks replaces old tasks (only HW 4 active)", task_names == ["HW 4"])

    tid = await database.upsert_inferred_task("CSE 21", "Final Project", "2026-06-01")
    check("upsert_inferred_task returns a valid ID", isinstance(tid, int) and tid > 0)

    ctx = await database.get_group_context("CSE 21")
    sources = {t["name"]: t["source"] for t in ctx["tasks"]}
    check("inferred task appears with source='inferred'", sources.get("Final Project") == "inferred")

    tid2 = await database.upsert_inferred_task("CSE 21", "Final Project", "2026-06-01")
    check("upsert_inferred_task is idempotent", tid == tid2)

    print("\n=== All tests passed ===\n")


if __name__ == "__main__":
    try:
        asyncio.run(run_tests())
    finally:
        os.unlink(database.DB_PATH)
