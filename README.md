# Deep Work Pilot

An agentic browser safeguard built for DiamondHacks 2026. Deep Work Pilot is a locally run, AI-powered "Chief of Staff" that monitors your browsing habits, intervenes when you visit blacklisted sites, and automatically sets up specific work environments (Groups) to keep you on task.

## Architecture
- **Language**: Python 3.13+
- **Core Engine**: Asyncio + `browser-use` SDK (v0.12.6)
- **Intelligence**: Google Gemini API (`gemini-flash-latest` & Vision capabilities)
- **Database**: SQLite (`aiosqlite`)
- **CLI Framework**: Basic interactive input (async-compatible)

## Setup & Installation

1. **Install dependencies using `uv`:**
   ```bash
   uv sync
   ```

2. **Set up your environment variables:**
   Copy `.env.example` to `.env` and fill in your details:
   ```bash
   cp .env.example .env
   ```
   *Required variables include `GEMINI_API_KEY`, `CHROME_PATH`, and `CHROME_PROFILE`.*

3. **Initialize the Database:**
   We provide a script to populate the local database with dummy tasks and blacklisted URLs.
   ```bash
   uv run seed_db.py
   ```

4. **Run the Pilot:**
   *Note: Ensure all regular Chrome instances using the same profile are closed before running to avoid locked database errors.*
   ```bash
   uv run main.py
   ```

## CLI Command Reference

The Pilot features an interactive command-line interface running concurrently with the watchdog.

### Group Management
*   **`group list`**: Displays all saved context groups.
*   **`group add <name> [description]`**: Creates a new group context.
*   **`group <name>`**: Shows detailed information for a specific group, including its description, URLs, and active tasks.

### URL & Tab Management
*   **`save <group> [count]`**: Captures open tabs and saves them to the specified group.
    *   *Example*: `save LeetCode` (Saves all tabs).
    *   *Example*: `save Research 3` (Saves only the 3 most recently opened/active tabs).
*   **`url list <group>`**: Lists all URLs currently linked to a group with indices.
*   **`url remove <group> <index/url>`**: Unlinks a URL from a group's context using its list index or the URL string.

### System & Task Tools
*   **`break [minutes]`**: Pauses the watchdog for a specified duration (default: 5 minutes), allowing you to browse freely without intervention.
*   **`override [url]`**: Forcefully unblacklists the specified URL (or the currently active tab if no URL is provided). This simulates the behavior of the "Override" popup.
*   **`audit`**: Manually triggers a check on the current active tab to see if it is classified as a distraction.
*   **`notion-sync [database_id]`**: Pulls tasks from a connected Notion database.
*   **`exit`**: Safely shuts down the watchdog and exits.
