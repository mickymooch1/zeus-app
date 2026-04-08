# Background Tasks System — Design Spec
**Date:** 2026-04-08
**Status:** Approved

## Overview

Enterprise-only background task system for Zeus. When a user asks for a long-running build (MultiAgentBuild), Zeus calls a `CreateBackgroundTask` tool instead of running the pipeline inline. The task runs in the background via `asyncio.create_task`, persists status to SQLite, emails the user on completion, and is viewable on a Tasks page in the web app.

---

## 1. Database

**File:** `backend/db.py`

New table added to `zeus.db` alongside existing `users` and `monthly_usage` tables.

```sql
CREATE TABLE IF NOT EXISTS tasks (
    id           TEXT PRIMARY KEY,
    user_id      TEXT NOT NULL,
    description  TEXT NOT NULL,
    status       TEXT NOT NULL DEFAULT 'pending',
    result       TEXT,
    live_url     TEXT,
    created_at   TEXT NOT NULL,
    completed_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_tasks_user ON tasks (user_id);
```

**Status values:** `pending` | `running` | `done` | `failed`

**`live_url`:** Netlify URL extracted from result text via regex (`https?://[^\s]+\.netlify\.app`). Nullable — set only when the Deployer agent returns a live URL.

**New functions:**

| Function | Signature | Purpose |
|---|---|---|
| `create_task` | `(db_path, user_id, description) -> dict` | Insert pending task, return row |
| `update_task` | `(db_path, task_id, **fields)` | Update any task fields |
| `get_task` | `(db_path, task_id) -> dict \| None` | Fetch single task |
| `get_tasks_for_user` | `(db_path, user_id) -> list` | All tasks for user, newest first |
| `fail_stale_tasks` | `(db_path)` | Mark any `running` tasks as `failed` at startup |

`init_user_tables` extended to create the `tasks` table and index.

---

## 2. Backend

### 2a. `CreateBackgroundTask` tool — `zeus_agent.py`

Added to `TOOLS` list (after `MultiAgentBuild`). Enterprise-only.

```
name: CreateBackgroundTask
inputs:
  request     string  required  — the full website build request
  description string  required  — short human-readable label for the task card
```

**Description text for Claude:**
> Schedule a MultiAgentBuild as a background task. Use this when the user asks for a website build that will take a long time. The pipeline runs in the background — the user is emailed when it completes. Enterprise plan only.

**ZEUS_SYSTEM_PROMPT addition:**

```
**CreateBackgroundTask(request, description)** — when a user asks for a MultiAgentBuild
or any task you estimate will take more than a few minutes, call this instead of
MultiAgentBuild. It schedules the pipeline in the background so the user doesn't
have to wait in the chat. The user will be emailed when the site is live.
Enterprise plan only.
```

### 2b. Inline handler in `run_turn_stream` — `zeus_agent.py`

Detected in the tool execution loop alongside `MultiAgentBuild`. The handler:

1. Enterprise gate — checks `subscription_status == "active"` and `subscription_plan == "enterprise"` via `db.get_user_by_id`. Returns error string if not enterprise.
2. Calls `db.create_task(db_path, user_id, description)` → returns task dict with UUID.
3. Defines `_run_background_task(task_id, request, user_id, history)` coroutine (local async def):
   - `db.update_task(..., status="running")`
   - Calls `run_multi_agent(request, _noop_on_message, history, user_id)` where `_noop_on_message` is `async def _(msg): pass` — the pipeline has already handed off to background; no live WebSocket to stream to.
   - On success: extracts Netlify URL from result with `re.search(r'https?://\S+\.netlify\.app', result)`, calls `db.update_task(..., status="done", result=result, live_url=url, completed_at=now)`, calls `_send_task_email(user_email, description, live_url, result)`.
   - On exception: `db.update_task(..., status="failed", result=str(exc), completed_at=now)`, logs error.
4. `asyncio.create_task(_run_background_task(...))`, added to a module-level `_bg_tasks: set = set()` in `zeus_agent.py` with `task.add_done_callback(_bg_tasks.discard)` to prevent GC of the running task.
5. Returns: `f"Background task queued — ID: {task_id}. I'll email you at {user_email} when it's done."`

### 2c. Email helper — `main.py`

`_send_task_email(user_email, description, live_url, result)` — plain function (not async, runs in background coroutine).

Uses `smtplib` + `GMAIL_USER` / `GMAIL_APP_PASSWORD` env vars (same as `SendEmail` tool in zeus_agent.py).

Subject: `"Zeus: Your background task is complete — {description}"`

Body:
```
Your background task has finished.

Task: {description}
Live URL: {live_url or "See result below"}

Result:
{result[:2000]}

— Zeus AI Design
```

If `GMAIL_USER` is not set: logs a warning and skips email silently (task still completes successfully).

### 2d. `GET /tasks` endpoint — `main.py`

```
GET /tasks
Auth: Bearer token required
Enterprise only: returns 403 with detail "Enterprise plan required" if not enterprise
Returns: list of task dicts, newest first
```

### 2e. Startup cleanup — `main.py`

`db.fail_stale_tasks(db_path)` called in the `lifespan` startup block after `db.init_user_tables(db_path)`.

---

## 3. Frontend

### 3a. `TasksPage.jsx` — new file

**Route:** `/tasks` (protected, enterprise-only)

**Enterprise gate:** On mount, checks `user.subscription_plan === 'enterprise' && user.subscription_status === 'active'`. If not enterprise, renders an upgrade prompt with a link to `/pricing`.

**Polling:** `useEffect` fetches `GET /tasks` on mount. If any task has status `pending` or `running`, starts a 10-second `setInterval` to re-fetch. Clears interval when all tasks are terminal (`done` or `failed`) or on unmount.

**Empty state:** `"No background tasks yet. Ask Zeus to build a website and it will appear here."`

**Task card fields:**
- Description
- Status badge: `⏳ Pending` · `🔄 Running` · `✅ Done` · `❌ Failed`
- Created time (ISO string — display as-is or formatted)
- If `done` + `live_url`: `<a href={live_url} target="_blank">View Live Site →</a>` styled as `btn btn-primary`
- If `failed`: result text in a muted error note

### 3b. Route added to `App.jsx`

```jsx
<Route path="/tasks" element={<ProtectedRoute><TasksPage /></ProtectedRoute>} />
```

### 3c. Navbar link

Link to `/tasks` added in `Navbar.jsx`. Visible only when `user` is present and `user.subscription_plan === 'enterprise'`.

---

## Error Handling

| Scenario | Behaviour |
|---|---|
| Railway restart mid-task | `fail_stale_tasks` marks `running` → `failed` on next startup |
| `run_multi_agent` throws | Caught in `_run_background_task`, status → `failed`, result = error message |
| Email send fails | Logged as warning, task still marked `done` |
| Non-enterprise user calls tool | Enterprise gate returns error string to Zeus, Zeus relays to user |
| `/tasks` called without enterprise | 403 HTTP response |

---

## Files Changed

| File | Change |
|---|---|
| `backend/db.py` | Add `tasks` table, 5 new functions, extend `init_user_tables` |
| `backend/zeus_agent.py` | Add `CreateBackgroundTask` to `TOOLS`, inline handler in `run_turn_stream`, update system prompt |
| `backend/main.py` | Add `_send_task_email`, `GET /tasks` endpoint, startup cleanup call |
| `web/src/pages/TasksPage.jsx` | New page |
| `web/src/App.jsx` | Add `/tasks` route |
| `web/src/components/Navbar.jsx` | Add Tasks link for enterprise users |
