# 🚀 Deep Work Pilot: Agentic Browser Safeguard
**DiamondHacks 2026 | Browser Use Track**

The **Deep Work Pilot** is an autonomous "Digital Chief of Staff" built on the **Browser Use SDK 3.0**. Unlike passive website blockers, this is an **Active Intervention Agent** that understands your academic context, monitors your behavior, and physically re-organizes your browser to keep you on task.

---

## 🛠️ System Architecture

The project operates as a **State Machine** running locally on Python, utilizing the Chrome DevTools Protocol (CDP) to "pilot" a real, authenticated Chrome instance.

### 1. The Tech Stack
* **Core:** Python 3.11+ (Asyncio-driven)
* **Agent:** [Browser Use SDK 3.0](https://github.com/browser-use/browser-use)
* **LLM:** Gemini 2.0 Flash (Vision-capable)
* **Database:** SQLite (Local persistence via `aiosqlite`)
* **Identity:** Real Chrome Profile (`user_data_dir`) for 2FA/Cookie persistence.

### 2. Logic Flow: The "Watchdog" Loop
1.  **Monitor:** Polls the active tab URL every 30-60 seconds.
2.  **Analyze:** If the URL is on the `Global_Blacklist` (e.g., YouTube), trigger the **Inference Engine**.
3.  **Infer:** The Agent navigates to the "Group Home" (e.g., Canvas) to see if there are active tasks/deadlines.
4.  **Intervene:** If procrastination is confirmed, the Agent injects a UI overlay and offers a "Switch to Workspace" action.
5.  **Restore:** The Agent closes distractions and opens the multi-tab environment (Canvas + Overleaf + Gemini) defined for that Course.

---

## 📂 Database Schema (SQLite)

We use a lean relational model to map URLs to Course Contexts.

| Table | Columns | Description |
| :--- | :--- | :--- |
| **Groups** | `id`, `name`, `description` | High-level contexts (e.g., "CSE 21", "Research"). |
| **URLs** | `id`, `url`, `is_blacklisted` | The web resources. Blacklist = Global distraction. |
| **Group_URLs** | `group_id`, `url_id` | Links "Seed URLs" (Piazza, Canvas) to a Course. |

> **Note on Tasks:** Specific assignment tasks are inferred live from the browser DOM (Canvas/Gradescope) by the Agent to ensure real-time accuracy without manual data entry.

---

## 🤖 Agent Commands (CLI Interface)

| Command | Action |
| :--- | :--- |
| `save [group]` | Captures all currently open/highlighted tabs and saves them to the DB as a new Workspace. |
| `mode [group]` | Triggers the Agent to close all non-essential tabs and launch the specific Course environment. |
| `audit` | Manually triggers a "Procrastination Check" on the current active tab. |
| `break [mins]` | Sets a temporary "Safe Zone" where the Watchdog ignores blacklisted URLs. |

---

## 🏗️ Repository Structure

```text
/deep-work-pilot
├── main.py              # The Async Event Loop & Watchdog Logic
├── database.py          # SQLite CRUD operations (aiosqlite)
├── agent_tools.py       # Custom @tools.actions for Browser Use SDK
├── schema.sql           # Database initialization script
├── .env                 # API Keys (GEMINI_API_KEY)
└── README.md            # Project Documentation