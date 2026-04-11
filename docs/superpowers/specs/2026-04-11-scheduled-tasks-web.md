# Scheduled Tasks — Web (Sub-project 1) Design Spec

**Goal:** Allow Pro, Agency, and Enterprise users to schedule Zeus to automatically run a task (e.g. rebuild their website) on a recurring cron schedule, managed through a new tab on the existing Tasks page.

**Architecture:** APScheduler `AsyncIOScheduler` runs inside FastAPI's asyncio event loop, reloading jobs from SQLite on every startup. A new `scheduler.py` module owns all scheduler logic. Five new API endpoints handle parse, CRUD, and toggle. The web frontend adds a two-tab layout to `TasksPage.jsx` and a new `ScheduledTasksTab.jsx` component.

---

## 1. Database

### New table: `scheduled_tasks`

Added to `db.py` `init_user_tables()` via `CREATE TABLE IF NOT EXISTS` — safe to run against existing databases.

```sql
CREATE TABLE IF NOT EXISTS scheduled_tasks (
    id               TEXT PRIMARY KEY,
    user_id          TEXT NOT NULL,
    task_description TEXT NOT NULL,
    cron_expression  TEXT NOT NULL,
    schedule_label   TEXT NOT NULL,
    timezone         TEXT NOT NULL DEFAULT 'UTC',
    is_active        INTEGER NOT NULL DEFAULT 1,
    last_run         TEXT,
    next_run         TEXT NOT NULL,
    created_at       TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_scheduled_tasks_user
    ON scheduled_tasks (user_id);
```

`timezone` is stored now and unused until timezone support is added — avoids a future migration.

### New DB functions in `db.py`

| Function | Purpose |
|---|---|
| `create_scheduled_task(db_path, user_id, task_description, cron_expression, schedule_label, next_run, timezone)` | Insert row, return dict |
| `get_scheduled_tasks_for_user(db_path, user_id)` | All tasks for user, `created_at DESC` |
| `get_all_active_scheduled_tasks(db_path)` | All rows where `is_active = 1` — used by scheduler on startup |
| `get_scheduled_task(db_path, task_id)` | Single row by ID |
| `update_scheduled_task(db_path, task_id, **fields)` | Update arbitrary columns |
| `delete_scheduled_task(db_path, task_id, user_id)` | Delete row owned by user; returns bool |
| `count_active_scheduled_tasks(db_path, user_id)` | Count `is_active = 1` rows — used for plan limit check |

---

## 2. Scheduler (`scheduler.py`)

A new module at `zeus-app/backend/scheduler.py`. The FastAPI app imports it; `main.py` calls `init_scheduler()` in the lifespan startup block and `shutdown_scheduler()` in teardown.

### Public interface

```python
def init_scheduler() -> None
def shutdown_scheduler() -> None
def add_job(task: dict) -> None        # called after POST /scheduled-tasks
def remove_job(task_id: str) -> None   # called after DELETE
def set_job_enabled(task_id: str, active: bool) -> None  # called after PATCH toggle
```

### Internal job runner

```python
async def _run_scheduled_task(task_id: str) -> None:
    db_path = db.get_db_path()
    task = db.get_scheduled_task(db_path, task_id)
    if not task or not task["is_active"]:
        return
    user = db.get_user_by_id(db_path, task["user_id"])
    if not user:
        return
    try:
        await _handle_create_background_task(
            request=task["task_description"],
            description=task["task_description"],
            history=history,           # imported from main via module-level ref
            user_id=task["user_id"],
        )
    except Exception:
        log.exception("_run_scheduled_task: task %s raised unexpectedly", task_id)
    finally:
        # Always advance the schedule — a failed run must not freeze next_run
        now = datetime.now(timezone.utc).isoformat()
        next_run = _compute_next_run(task["cron_expression"])
        db.update_scheduled_task(db_path, task_id, last_run=now, next_run=next_run)
```

**Thread safety:** `_run_scheduled_task` is `async def`. `AsyncIOScheduler` schedules async job functions directly in the event loop — no thread pool is used. SQLite WAL mode (already enabled in `db.py`) safely handles concurrent coroutine writes. This guarantee holds only because the job function is `async def`; synchronous job functions would be dispatched to a thread pool.

### Cron helper

```python
def _compute_next_run(cron_expression: str) -> str:
    """Return the next fire time as an ISO datetime string (UTC)."""
    from croniter import croniter
    now = datetime.now(timezone.utc)
    return croniter(cron_expression, now).get_next(datetime).isoformat()
```

### Startup load

`init_scheduler()` fetches all active scheduled tasks from the DB and calls `add_job()` for each. This makes restarts safe — no in-memory state is needed between processes.

---

## 3. API Endpoints

All endpoints in `main.py`. Auth via `Depends(auth.get_current_user)` throughout.

### Plan gate helper

```python
_SCHEDULED_TASK_LIMITS = {"pro": 5, "agency": 20, "enterprise": None}

def _scheduled_task_plan_allowed(user: dict) -> bool:
    plan = user.get("subscription_plan")
    status = user.get("subscription_status", "free")
    is_admin = bool(user.get("is_admin", 0))
    return is_admin or (status == "active" and plan in _SCHEDULED_TASK_LIMITS)

def _scheduled_task_limit(user: dict) -> int | None:
    """Returns max active tasks for user's plan, or None for unlimited."""
    if user.get("is_admin"):
        return None
    return _SCHEDULED_TASK_LIMITS.get(user.get("subscription_plan"))
```

---

### `POST /scheduled-tasks/parse`

Auth required, no plan gate (Free users can preview; the gate is on creation).

**Request:** `{"natural_language": "every Monday at 9am"}`

**Cache:** module-level `_parse_cache: dict[str, dict] = {}` in `main.py`, keyed on `natural_language.lower().strip()`. Return cached result immediately if present.

**Claude call:** Single-turn Anthropic API call (not a full agent loop) with a tightly constrained system prompt:

```
You extract cron expressions from natural language schedule descriptions.
Respond with ONLY a JSON object: {"cron_expression": "...", "schedule_label": "..."}
- cron_expression: standard 5-field cron (minute hour day month weekday)
- schedule_label: concise human-readable label, e.g. "Every Monday at 9am"
If you cannot parse the input into a valid cron expression, respond with:
{"error": "Could not parse schedule — try something like 'every Monday at 9am'"}
Do not include any other text.
```

**Response:** `{"cron_expression": "0 9 * * 1", "schedule_label": "Every Monday at 9am"}` on success, HTTP 400 with `{"detail": "..."}` if Claude returns an error field.

---

### `POST /scheduled-tasks`

**Plan gate:** 403 if `_scheduled_task_plan_allowed` is false.
**Limit check:** Count active tasks; if at or above plan limit, return 403 with message: `"You've reached the limit of {limit} scheduled tasks on the {plan} plan. Upgrade to add more."`

**Request:**
```json
{
  "task_description": "Rebuild my bakery website",
  "cron_expression": "0 9 * * 1",
  "schedule_label": "Every Monday at 9am",
  "timezone": "UTC"
}
```

Server-side: validates `cron_expression` is parseable by `croniter` (400 if not), computes `next_run`, inserts DB row, calls `scheduler.add_job(task)`.

**Response:** The created task row as a dict.

---

### `GET /scheduled-tasks`

**Plan gate:** 403 if not allowed.

**Response:** Array of task dicts for the logged-in user, `created_at DESC`.

---

### `DELETE /scheduled-tasks/{id}`

**Plan gate:** 403 if not allowed.

Calls `db.delete_scheduled_task` (user-scoped delete), then `scheduler.remove_job(id)`. 404 if not found or not owned by user.

**Response:** `{"ok": true}`

---

### `PATCH /scheduled-tasks/{id}/toggle`

**Plan gate:** 403 if not allowed.
**Re-activation limit check:** If toggling on, check count again — prevents a user from circumventing limits by deactivating and reactivating.

Flips `is_active`. If activating: recomputes `next_run`, calls `scheduler.set_job_enabled(id, True)`. If deactivating: calls `scheduler.set_job_enabled(id, False)`.

**Response:** Updated task row as a dict.

---

## 4. Web Frontend

### `TasksPage.jsx` changes

Add a tab switcher at the top of the page with two tabs: **Background Tasks** (existing content, untouched) and **Scheduled Tasks** (new). Active tab stored in `useState`. Default tab: Background Tasks (preserves existing behaviour for existing users).

### New component: `ScheduledTasksTab.jsx`

`zeus-app/web/src/components/ScheduledTasksTab.jsx`

**Layout (top to bottom):**

1. **Create form** — always visible at the top
2. **Task list** — existing scheduled tasks below

#### Create form

```
[ What should Zeus do?                              ]  ← textarea
[ Describe your schedule (e.g. every Monday 9am)   ]  ← text input
[ Parse ↺ ]                                            ← button, spinner while loading
✓ Every Monday at 9am                                  ← appears after successful parse
[ Create Task ]                                        ← appears after successful parse
```

- Parse button shows a spinner and is disabled while the API call is in flight (prevents double-submit)
- If the schedule input changes after a successful parse, the confirmed label and Create Task button disappear — user must re-parse
- On successful Create Task, the form resets and the new task appears at the top of the list
- 403 responses render as an inline banner: `"Scheduled tasks require a Pro plan or above — upgrade at zeusaidesign.com/pricing."`
- Limit-reached 403s render the server's message verbatim

#### Task list

Each row:
- **Schedule label** (bold) + task description
- **Status badge**: green "Active" / grey "Paused"
- **Next run**: formatted datetime (or "—" if paused)
- **Last run**: formatted datetime (or "Never")
- **Toggle switch**: calls `PATCH /scheduled-tasks/{id}/toggle`
- **Delete button**: calls `DELETE /scheduled-tasks/{id}`, removes from list optimistically

Empty state: "No scheduled tasks yet. Create one above."

Loading state: spinner while initial fetch is in progress.

#### Data flow

`ScheduledTasksTab` fetches `GET /scheduled-tasks` on mount. All mutations (create, toggle, delete) update local state immediately (optimistic) and revert on error.

---

## 5. Files Changed / Created

| Action | File | Change |
|---|---|---|
| Modify | `zeus-app/backend/db.py` | Add `scheduled_tasks` table + 7 new functions |
| Create | `zeus-app/backend/scheduler.py` | AsyncIOScheduler, job management, `_run_scheduled_task` |
| Modify | `zeus-app/backend/main.py` | 5 endpoints, parse cache, plan gate helpers, lifespan hooks |
| Modify | `zeus-app/web/src/pages/TasksPage.jsx` | Tab switcher, render `ScheduledTasksTab` |
| Create | `zeus-app/web/src/components/ScheduledTasksTab.jsx` | Full scheduled tasks UI |

---

## 6. Dependencies

- `apscheduler>=3.10.0` — add to `zeus-app/backend/requirements.txt`
- `croniter>=2.0.0` — add to `zeus-app/backend/requirements.txt`

Both are pure Python, no native extensions, Railway-compatible.

---

## 7. Error Handling

| Scenario | Behaviour |
|---|---|
| Invalid cron expression on create | 400: "Invalid cron expression" |
| Claude can't parse natural language | 400 with Claude's error message |
| Claude API timeout on parse | 400: "Schedule parsing timed out — try again" |
| Scheduler job fires, pipeline fails | `finally` block always updates `last_run`/`next_run`; task stays scheduled |
| Server restarts mid-run | Task marked `running` in background tasks table; `fail_stale_tasks` cleans it up on next startup; scheduled task's `last_run`/`next_run` unchanged until next fire |
| Free user hits parse or create | 403 → inline upgrade banner in UI |
| User at plan limit tries to create | 403 → inline message with current limit and plan name |
