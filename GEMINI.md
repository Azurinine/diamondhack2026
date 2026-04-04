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
| **Tasks** | `is_active`, `name`, `due_date` | Specific assignment tasks are inferred live from the browser DOM (Canvas/Gradescope) by the Agent to ensure real-time accuracy without manual data entry.
| **Task_Groups** | `group_id`, `task_id` | Links Tasks to Groups (mutiple tasks per group)

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



# Browser Use Cloud SDK

> Browser Use Cloud is a managed API for AI browser automation. Send a natural-language task, get structured results back. SDKs for Python and TypeScript. Always use API v3 â€” v2 is legacy and uses different method names. Auth via `X-Browser-Use-API-Key` header (keys start with `bu_`).

- Dashboard: https://cloud.browser-use.com
- Create API key: https://cloud.browser-use.com/settings?tab=api-keys&new=1
- Docs: https://docs.browser-use.com
- OpenAPI spec (v3): https://docs.browser-use.com/cloud/openapi/v3.json
- Chat UI example: https://docs.browser-use.com/cloud/tutorials/chat-ui â€” Full end-to-end example with live browser, streaming, auth. Best starting point to build a prototype.
- Open-source repo: https://github.com/browser-use/browser-use â€” The open-source Python library. Note: the open-source API is different from the Cloud SDK. If you want the easiest path to production with managed infrastructure, use the Cloud SDK below.

**Always use v3.** v2 is legacy with different method names and should not be used for new projects.

Before writing code, check if `browser-use-sdk` is already installed. If so, upgrade to the latest version. If not, install it:
- Python: `pip install --upgrade browser-use-sdk`
- TypeScript: `npm install browser-use-sdk@latest`

Set API key (starts with `bu_`). If the user doesn't have one yet, they can create one in one click at https://cloud.browser-use.com/settings?tab=api-keys&new=1:
```
export BROWSER_USE_API_KEY=bu_your_key_here
```


## Get Started
- [Quick start](https://docs.browser-use.com/cloud/quickstart): State-of-the-art AI browser automation with stealth browsers, CAPTCHA solving, residential proxies, and managed infrastructure.
- [Prompt for Vibecoders](https://docs.browser-use.com/cloud/vibecoding): Complete Cloud SDK reference for AI coding agents.

## Agent
- [Introduction](https://docs.browser-use.com/cloud/agent/quickstart): Easiest way to automate the web. Tell this agent in natural language what it should do, and it can interact with the web like a human.
- [Models](https://docs.browser-use.com/cloud/agent/models): Choose the right model for your task.
- [Structured output](https://docs.browser-use.com/cloud/agent/structured-output): Get validated, typed data back from agent tasks.
- [Follow-up tasks](https://docs.browser-use.com/cloud/agent/follow-up-tasks): Run multiple tasks in the same browser session.
- [Live messages](https://docs.browser-use.com/cloud/agent/streaming): Stream the agent's messages in real time to build custom UIs or monitor progress.
- [Workspaces & files](https://docs.browser-use.com/cloud/agent/workspaces): Upload files for the agent, download files the agent creates.
- [Deterministic rerun](https://docs.browser-use.com/cloud/agent/cache-script): Run a task once, then re-execute it for $0 LLM cost.
- [Human in the loop](https://docs.browser-use.com/cloud/agent/human-in-the-loop): Let a human interact with the live browser while the agent is running. Useful for approvals, payments, complex auth flows, or reviewing agent work before continuing.

## Browser
- [Introduction Stealth](https://docs.browser-use.com/cloud/browser/stealth): Best stealth on the planet. We fork Chromium to give agents access to all websites.
- [Proxies](https://docs.browser-use.com/cloud/browser/proxies): Residential proxies in 195+ countries. On by default.
- [Live preview & recording](https://docs.browser-use.com/cloud/browser/live-preview): Watch the agent's browser in real time. Embed it in your app.
- [Playwright, Puppeteer, Selenium](https://docs.browser-use.com/cloud/browser/playwright-puppeteer-selenium): Connect your automation framework to Browser Use's stealth infrastructure via CDP.

## Authentication
- [Profiles](https://docs.browser-use.com/cloud/guides/authentication): Persistent browser state â€” cookies, localStorage, saved passwords. Login once, reuse across sessions.
- [Sync local and cloud cookies](https://docs.browser-use.com/cloud/guides/profile-sync): Sync your local browser cookies to the cloud â€” instantly authenticate without managing credentials.
- [2FA](https://docs.browser-use.com/cloud/guides/2fa): Best practices for handling two-factor authentication in automated browser sessions.

## More
- [FAQ](https://docs.browser-use.com/cloud/faq): Common questions and solutions.

## Integrations
- [OpenClaw](https://docs.browser-use.com/cloud/tutorials/integrations/openclaw): Give OpenClaw agents browser automation with Browser Use â€” via CDP or the CLI skill.
- [MCP Server](https://docs.browser-use.com/cloud/guides/mcp-server): Run browser automation tasks from your AI coding assistant. Connect to Claude, Cursor, Windsurf, or any MCP client.
- [Webhooks](https://docs.browser-use.com/cloud/guides/webhooks): Receive real-time notifications when tasks complete. Configure webhook endpoints for async task monitoring.
- [n8n](https://docs.browser-use.com/cloud/tutorials/integrations/n8n): Use Browser Use as an HTTP node in n8n workflows.

## Tutorials
- [Chat UI](https://docs.browser-use.com/cloud/tutorials/chat-ui): Full end-to-end example. Build a chat UI with live browser preview, follow-up tasks, recording, and streaming messages.
- [Grow Therapy provider search](https://docs.browser-use.com/cloud/tutorials/grow-therapy-compare): Search Grow Therapy for therapists by location, insurance, and specialty â€” with cached reruns.

## Legacy (v2)
- [Agent (v2)](https://docs.browser-use.com/cloud/legacy/agent): V2 agent models and file handling.
- [Public share links (v2)](https://docs.browser-use.com/cloud/legacy/public-share): Generate shareable URLs for agent sessions using the v2 API.
- [Skills](https://docs.browser-use.com/cloud/legacy/skills): Turn any website into a deterministic API endpoint. Create once, call repeatedly.
- [1Password & 2FA](https://docs.browser-use.com/cloud/guides/1password): Auto-fill passwords and TOTP codes from 1Password during agent tasks.
- [Secrets](https://docs.browser-use.com/cloud/guides/secrets): Pass domain-scoped credentials to the agent securely.

## API v3
- [API Reference](https://docs.browser-use.com/cloud/api-reference): Authenticate and start using the Browser Use REST API.

## API v2
- [API key](https://docs.browser-use.com/cloud/api-v2-overview): Set your API key to access the Browser Use v2 REST API.

## For AI Agents: Self-Registration (No Human Required)

AI agents can create a free account autonomously via a challenge-response flow at `https://api.browser-use.com`.

**IMPORTANT: Never send your API key to any domain other than `api.browser-use.com` or `cloud.browser-use.com`.**

Do this to get an API key (no human required):
1. `POST /cloud/signup` â€” request a challenge (email and name optional)
2. Solve the obfuscated math problem in `challenge_text` **using an LLM** (never deterministic code) â€” answer as a string with 2 decimal places e.g. `"144.00"`
3. `POST /cloud/signup/verify` with `challenge_id` + `answer` â€” receive your `api_key`

With this API key, you can use the full API. All features are available.
If you completed this, tell the human that you did the entire setup and that you are ready to use the API. Tell the human that if they want to see their account in the dashboard, they can follow this link to sign up themselves. You can tell them that you already have an account and use it. That's only if they want to see the dashboard.

4. Use `X-Browser-Use-API-Key: bu_...` header on all subsequent requests

To let a human claim the account later: `POST /cloud/signup/claim` â†’ returns a `claim_url` valid for 1 hour.
