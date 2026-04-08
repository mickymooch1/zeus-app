# Background Tasks System Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add enterprise-only background task execution so Zeus can schedule long-running MultiAgentBuild pipelines asynchronously, persist their status to SQLite, email users on completion, and display results on a Tasks page.

**Architecture:** Zeus calls a new `CreateBackgroundTask` tool, which is handled inline in `run_turn_stream` — the same pattern used for `MultiAgentBuild`. The handler writes a `pending` record to the `tasks` table, spawns `asyncio.create_task(run_multi_agent(...))`, and immediately returns a confirmation to the user. The background coroutine updates task status in SQLite and sends a Gmail SMTP notification on completion.

**Tech Stack:** Python (asyncio, smtplib, sqlite3), FastAPI, React + React Router, existing `HistoryStore` / `db.py` / `zeus_agent.py` / `main.py` patterns.

---

## File Map

| File | Action | Responsibility |
|---|---|---|
| `backend/db.py` | Modify | Add `tasks` table to `init_user_tables`, add 5 task CRUD functions |
| `backend/zeus_agent.py` | Modify | Add `_bg_tasks` set, `CreateBackgroundTask` tool + system prompt + inline handler |
| `backend/main.py` | Modify | Add `_send_task_email`, `GET /tasks` endpoint, startup `fail_stale_tasks` call |
| `backend/tests/test_db_tasks.py` | Create | Unit tests for all db task functions |
| `backend/tests/test_tasks_endpoint.py` | Create | Integration tests for `GET /tasks` endpoint |
| `web/src/pages/TasksPage.jsx` | Create | Tasks list page with polling and status badges |
| `web/src/App.jsx` | Modify | Add `/tasks` route |
| `web/src/components/Navbar.jsx` | Modify | Add Tasks link for enterprise users |

---

### Task 1: Add `tasks` table and CRUD functions to `db.py`

**Files:**
- Modify: `backend/db.py`
- Create: `backend/tests/test_db_tasks.py`

- [ ] **Step 1: Write failing tests for db task functions**

Create `backend/tests/test_db_tasks.py`:

```python
import pytest
import tempfile
import pathlib
from datetime import datetime, timezone

import sys
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

import db


@pytest.fixture
def db_path(tmp_path):
    path = tmp_path / "test_zeus.db"
    db.init_user_tables(path)
    return path


@pytest.fixture
def user_id():
    return "test-user-123"


class TestCreateTask:
    def test_returns_dict_with_expected_fields(self, db_path, user_id):
        task = db.create_task(db_path, user_id, "Build site for Acme")
        assert task["id"]
        assert task["user_id"] == user_id
        assert task["description"] == "Build site for Acme"
        assert task["status"] == "pending"
        assert task["result"] is None
        assert task["live_url"] is None
        assert task["created_at"]
        assert task["completed_at"] is None

    def test_id_is_unique(self, db_path, user_id):
        t1 = db.create_task(db_path, user_id, "Task A")
        t2 = db.create_task(db_path, user_id, "Task B")
        assert t1["id"] != t2["id"]


class TestUpdateTask:
    def test_updates_status(self, db_path, user_id):
        task = db.create_task(db_path, user_id, "Build site")
        db.update_task(db_path, task["id"], status="running")
        updated = db.get_task(db_path, task["id"])
        assert updated["status"] == "running"

    def test_updates_result_and_live_url(self, db_path, user_id):
        task = db.create_task(db_path, user_id, "Build site")
        now = datetime.now(timezone.utc).isoformat()
        db.update_task(
            db_path, task["id"],
            status="done",
            result="Live at https://acme-corp.netlify.app",
            live_url="https://acme-corp.netlify.app",
            completed_at=now,
        )
        updated = db.get_task(db_path, task["id"])
        assert updated["status"] == "done"
        assert updated["live_url"] == "https://acme-corp.netlify.app"
        assert updated["completed_at"] == now


class TestGetTask:
    def test_returns_none_for_missing_id(self, db_path):
        assert db.get_task(db_path, "nonexistent-id") is None

    def test_returns_task_by_id(self, db_path, user_id):
        task = db.create_task(db_path, user_id, "Build site")
        fetched = db.get_task(db_path, task["id"])
        assert fetched["id"] == task["id"]


class TestGetTasksForUser:
    def test_returns_empty_list_for_new_user(self, db_path):
        assert db.get_tasks_for_user(db_path, "no-tasks-user") == []

    def test_returns_only_user_tasks(self, db_path):
        db.create_task(db_path, "user-a", "Task for A")
        db.create_task(db_path, "user-b", "Task for B")
        tasks = db.get_tasks_for_user(db_path, "user-a")
        assert len(tasks) == 1
        assert tasks[0]["user_id"] == "user-a"

    def test_returns_newest_first(self, db_path, user_id):
        db.create_task(db_path, user_id, "First task")
        db.create_task(db_path, user_id, "Second task")
        tasks = db.get_tasks_for_user(db_path, user_id)
        assert tasks[0]["description"] == "Second task"


class TestFailStaleTasks:
    def test_marks_running_tasks_as_failed(self, db_path, user_id):
        task = db.create_task(db_path, user_id, "Stale task")
        db.update_task(db_path, task["id"], status="running")
        db.fail_stale_tasks(db_path)
        updated = db.get_task(db_path, task["id"])
        assert updated["status"] == "failed"
        assert updated["completed_at"] is not None

    def test_does_not_touch_pending_or_done_tasks(self, db_path, user_id):
        pending = db.create_task(db_path, user_id, "Pending task")
        done = db.create_task(db_path, user_id, "Done task")
        db.update_task(db_path, done["id"], status="done")
        db.fail_stale_tasks(db_path)
        assert db.get_task(db_path, pending["id"])["status"] == "pending"
        assert db.get_task(db_path, done["id"])["status"] == "done"
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
cd C:/Users/Student/zeus-app/backend
python -m pytest tests/test_db_tasks.py -v 2>&1 | head -30
```

Expected: `ImportError` or `AttributeError: module 'db' has no attribute 'create_task'`

- [ ] **Step 3: Extend `init_user_tables` with the tasks table**

In `backend/db.py`, replace:
```python
def init_user_tables(db_path: pathlib.Path) -> None:
    """Create users and monthly_usage tables if they don't exist."""
    conn = _conn(db_path)
    try:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS users (
```

with:
```python
def init_user_tables(db_path: pathlib.Path) -> None:
    """Create users, monthly_usage, and tasks tables if they don't exist."""
    conn = _conn(db_path)
    try:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS users (
```

Then inside the same `executescript` string, after the `monthly_usage` table definition and before the closing `"""`), add:

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

- [ ] **Step 4: Add the five task functions at the bottom of `db.py`**

Append after `reset_monthly_usage`:

```python
# ── Background task CRUD ──────────────────────────────────────────────────────

def create_task(db_path: pathlib.Path, user_id: str, description: str) -> dict:
    """Insert a new pending task and return the row as a dict."""
    import uuid as _uuid
    now = datetime.now(timezone.utc).isoformat()
    task_id = str(_uuid.uuid4())
    conn = _conn(db_path)
    try:
        conn.execute(
            """
            INSERT INTO tasks (id, user_id, description, status, created_at)
            VALUES (?, ?, ?, 'pending', ?)
            """,
            (task_id, user_id, description, now),
        )
        conn.commit()
        return get_task(db_path, task_id)
    finally:
        conn.close()


def update_task(db_path: pathlib.Path, task_id: str, **fields) -> None:
    """Update one or more columns on a task row."""
    if not fields:
        return
    set_clause = ", ".join(f"{k} = ?" for k in fields)
    values = list(fields.values()) + [task_id]
    conn = _conn(db_path)
    try:
        conn.execute(f"UPDATE tasks SET {set_clause} WHERE id = ?", values)
        conn.commit()
    finally:
        conn.close()


def get_task(db_path: pathlib.Path, task_id: str) -> dict | None:
    """Fetch a single task by ID."""
    conn = _conn(db_path)
    try:
        row = conn.execute(
            "SELECT * FROM tasks WHERE id = ?", (task_id,)
        ).fetchone()
        return _row_to_dict(row)
    finally:
        conn.close()


def get_tasks_for_user(db_path: pathlib.Path, user_id: str) -> list:
    """Return all tasks for a user, newest first."""
    conn = _conn(db_path)
    try:
        rows = conn.execute(
            "SELECT * FROM tasks WHERE user_id = ? ORDER BY created_at DESC",
            (user_id,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def fail_stale_tasks(db_path: pathlib.Path) -> None:
    """Mark any 'running' tasks as 'failed' — called at startup after a restart."""
    now = datetime.now(timezone.utc).isoformat()
    conn = _conn(db_path)
    try:
        conn.execute(
            "UPDATE tasks SET status = 'failed', completed_at = ? WHERE status = 'running'",
            (now,),
        )
        conn.commit()
    finally:
        conn.close()
```

- [ ] **Step 5: Run tests — all should pass**

```bash
cd C:/Users/Student/zeus-app/backend
python -m pytest tests/test_db_tasks.py -v
```

Expected: all 11 tests pass.

- [ ] **Step 6: Commit**

```bash
cd C:/Users/Student/zeus-app
git add backend/db.py backend/tests/test_db_tasks.py
git commit -m "feat: add tasks table and CRUD functions to db.py"
```

---

### Task 2: Add `CreateBackgroundTask` tool to `zeus_agent.py`

**Files:**
- Modify: `backend/zeus_agent.py`

- [ ] **Step 1: Add `_bg_tasks` module-level set**

In `backend/zeus_agent.py`, find the line:
```python
_anthropic_client: anthropic.AsyncAnthropic | None = None
```

Add directly below it:
```python
# Holds references to background task coroutines so they aren't GC'd mid-run
_bg_tasks: set = set()
```

- [ ] **Step 2: Add `CreateBackgroundTask` to the TOOLS list**

In `backend/zeus_agent.py`, find the end of the `TOOLS` list — the closing `]` after the `MultiAgentBuild` entry and the `_RESEARCHER_TOOLS` / `_BUILDER_TOOLS` / `_DEPLOYER_TOOLS` lines. Add the new tool **inside** the `TOOLS` list, immediately after `MultiAgentBuild`:

```python
    {
        "name": "CreateBackgroundTask",
        "description": (
            "Schedule a MultiAgentBuild as a background task. "
            "Use this when the user asks for a website build that will take a long time. "
            "The pipeline runs in the background — the user is emailed at their registered "
            "address when the site is live. Returns immediately with a task ID. "
            "Enterprise plan only."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "request": {
                    "type": "string",
                    "description": "The full website build request to pass to the MultiAgentBuild pipeline",
                },
                "description": {
                    "type": "string",
                    "description": "Short human-readable label for the task card, e.g. 'Build website for Joe's Plumbing'",
                },
            },
            "required": ["request", "description"],
        },
    },
```

- [ ] **Step 3: Update ZEUS_SYSTEM_PROMPT**

In `backend/zeus_agent.py`, find the line inside `ZEUS_SYSTEM_PROMPT`:
```
**UpsertProject(name, ...)** — log every website you build
```

Add above it:

```
**CreateBackgroundTask(request, description)** — when a user asks for a MultiAgentBuild
or any website build you estimate will take more than a few minutes, call this instead
of MultiAgentBuild directly. It schedules the pipeline in the background so the user
doesn't have to wait in the chat. The user will be emailed at their registered address
when the site is live. Enterprise plan only.

```

- [ ] **Step 4: Add inline handler for `CreateBackgroundTask` in `run_turn_stream`**

In `backend/zeus_agent.py`, find the existing `MultiAgentBuild` inline handler in `run_turn_stream`:

```python
                # MultiAgentBuild is async — handle inline rather than via _run_tool
                if tb["name"] == "MultiAgentBuild":
                    result = await run_multi_agent(
                        request=tb["input"].get("request", ""),
                        on_message=on_message,
                        history=history,
                        user_id=user_id,
                    )
                else:
                    result = _run_tool(tb["name"], tb["input"], history)
```

Replace with:

```python
                # Async tools — handle inline rather than via _run_tool
                if tb["name"] == "MultiAgentBuild":
                    result = await run_multi_agent(
                        request=tb["input"].get("request", ""),
                        on_message=on_message,
                        history=history,
                        user_id=user_id,
                    )
                elif tb["name"] == "CreateBackgroundTask":
                    result = await _handle_create_background_task(
                        request=tb["input"].get("request", ""),
                        description=tb["input"].get("description", "Background build"),
                        history=history,
                        user_id=user_id,
                    )
                else:
                    result = _run_tool(tb["name"], tb["input"], history)
```

- [ ] **Step 5: Add `_handle_create_background_task` function**

Add this function immediately before `run_turn_stream` (after `run_multi_agent`):

```python
async def _handle_create_background_task(
    request: str,
    description: str,
    history: "HistoryStore",
    user_id: str | None,
) -> str:
    """
    Create a background task record and spawn run_multi_agent as an asyncio task.
    Returns immediately with a confirmation string for Zeus to relay to the user.
    Enterprise plan only.
    """
    import db as _db

    if not user_id:
        return "Error: Cannot create background task — no authenticated user."

    # Enterprise gate
    try:
        _db_path = _db.get_db_path()
        _user = _db.get_user_by_id(_db_path, user_id)
        if not _user:
            return "Error: User not found."
        _plan = _user.get("subscription_plan") or "free"
        _status = _user.get("subscription_status", "free")
        if not (_status == "active" and _plan == "enterprise"):
            return (
                "❌ **CreateBackgroundTask requires an Enterprise plan.** "
                "Upgrade at zeusaidesign.com/pricing."
            )
        user_email = _user.get("email", "")
    except Exception as exc:
        log.warning("_handle_create_background_task: could not verify plan: %s", exc)
        return f"Error: Could not verify enterprise plan — {exc}"

    # Create the DB record
    try:
        task = _db.create_task(_db_path, user_id, description)
        task_id = task["id"]
    except Exception as exc:
        log.error("_handle_create_background_task: db.create_task failed: %s", exc)
        return f"Error: Could not create task record — {exc}"

    # Background coroutine — runs after this function returns
    async def _run() -> None:
        try:
            _db.update_task(_db_path, task_id, status="running")

            # Noop sink — no live WebSocket to stream to in background
            async def _noop(_msg: dict) -> None:
                pass

            result_text = await run_multi_agent(request, _noop, history, user_id)

            # Extract Netlify URL from result
            import re as _re
            _match = _re.search(r'https?://\S+\.netlify\.app', result_text)
            live_url = _match.group(0).rstrip(".,)") if _match else None

            now = datetime.now().isoformat()
            _db.update_task(
                _db_path, task_id,
                status="done",
                result=result_text,
                live_url=live_url,
                completed_at=now,
            )
            log.info("Background task %s done. live_url=%s", task_id, live_url)

            # Email notification (imported here to avoid circular import)
            try:
                from main import _send_task_email
                _send_task_email(user_email, description, live_url, result_text)
            except Exception as email_exc:
                log.warning("Background task %s: email failed: %s", task_id, email_exc)

        except Exception as exc:
            log.error("Background task %s failed: %s", task_id, exc)
            now = datetime.now().isoformat()
            try:
                _db.update_task(
                    _db_path, task_id,
                    status="failed",
                    result=str(exc),
                    completed_at=now,
                )
            except Exception:
                log.exception("Background task %s: could not update failed status", task_id)

    bg = asyncio.create_task(_run())
    _bg_tasks.add(bg)
    bg.add_done_callback(_bg_tasks.discard)

    return (
        f"✅ Background task queued — ID: `{task_id}`\n"
        f"I'll email you at **{user_email}** when it's done.\n"
        f"You can track progress at [/tasks](/tasks)."
    )
```

- [ ] **Step 6: Add `import asyncio` at the top of `zeus_agent.py` if not already present**

Check the imports section — `asyncio` is not currently imported. Add it:

Find:
```python
import json
import logging
import os
```

Replace with:
```python
import asyncio
import json
import logging
import os
```

- [ ] **Step 7: Smoke-test the import**

```bash
cd C:/Users/Student/zeus-app/backend
python -c "from zeus_agent import _handle_create_background_task, _bg_tasks; print('OK')"
```

Expected: `OK`

- [ ] **Step 8: Commit**

```bash
cd C:/Users/Student/zeus-app
git add backend/zeus_agent.py
git commit -m "feat: add CreateBackgroundTask tool and handler to zeus_agent"
```

---

### Task 3: Add `_send_task_email`, `GET /tasks`, and startup cleanup to `main.py`

**Files:**
- Modify: `backend/main.py`
- Create: `backend/tests/test_tasks_endpoint.py`

- [ ] **Step 1: Write failing endpoint tests**

Create `backend/tests/test_tasks_endpoint.py`:

```python
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient


def _make_enterprise_user():
    return {
        "id": "ent-user-1",
        "email": "test@example.com",
        "subscription_status": "active",
        "subscription_plan": "enterprise",
        "password_hash": "x",
    }


def _make_free_user():
    return {
        "id": "free-user-1",
        "email": "free@example.com",
        "subscription_status": "free",
        "subscription_plan": None,
        "password_hash": "x",
    }


class TestTasksEndpoint:
    def test_requires_auth(self):
        from main import app
        with TestClient(app) as client:
            resp = client.get("/tasks")
        assert resp.status_code == 401

    def test_enterprise_user_gets_empty_list(self):
        from main import app
        import auth
        with patch("auth.get_current_user", return_value=_make_enterprise_user()), \
             patch("db.get_tasks_for_user", return_value=[]):
            with TestClient(app) as client:
                resp = client.get(
                    "/tasks",
                    headers={"Authorization": "Bearer fake-token"},
                )
        assert resp.status_code == 200
        assert resp.json() == []

    def test_non_enterprise_gets_403(self):
        from main import app
        with patch("auth.get_current_user", return_value=_make_free_user()):
            with TestClient(app) as client:
                resp = client.get(
                    "/tasks",
                    headers={"Authorization": "Bearer fake-token"},
                )
        assert resp.status_code == 403

    def test_returns_tasks_for_user(self):
        from main import app
        mock_tasks = [
            {
                "id": "task-1",
                "user_id": "ent-user-1",
                "description": "Build site for Acme",
                "status": "done",
                "result": "Live at https://acme.netlify.app",
                "live_url": "https://acme.netlify.app",
                "created_at": "2026-04-09T10:00:00",
                "completed_at": "2026-04-09T10:30:00",
            }
        ]
        with patch("auth.get_current_user", return_value=_make_enterprise_user()), \
             patch("db.get_tasks_for_user", return_value=mock_tasks):
            with TestClient(app) as client:
                resp = client.get(
                    "/tasks",
                    headers={"Authorization": "Bearer fake-token"},
                )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["live_url"] == "https://acme.netlify.app"
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
cd C:/Users/Student/zeus-app/backend
python -m pytest tests/test_tasks_endpoint.py -v 2>&1 | head -20
```

Expected: failures because `/tasks` route does not exist yet.

- [ ] **Step 3: Add `_send_task_email` helper to `main.py`**

In `backend/main.py`, find:
```python
_RAILWAY = bool(os.environ.get("RAILWAY_ENVIRONMENT") or os.environ.get("RAILWAY_PROJECT_ID"))
```

Add above it:

```python
def _send_task_email(
    user_email: str,
    description: str,
    live_url: str | None,
    result: str,
) -> None:
    """Send a task completion email via Gmail SMTP. Silently skips if not configured."""
    import smtplib
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart

    smtp_email = os.environ.get("SMTP_EMAIL", "").strip()
    smtp_password = os.environ.get("SMTP_PASSWORD", "").strip()
    if not smtp_email or not smtp_password:
        log.warning("_send_task_email: SMTP_EMAIL/SMTP_PASSWORD not set — skipping")
        return

    subject = f"Zeus: Your background task is complete — {description}"
    body_lines = [
        "Your background task has finished.",
        "",
        f"Task: {description}",
        f"Live URL: {live_url or 'See result below'}",
        "",
        "Result:",
        result[:2000],
        "",
        "— Zeus AI Design",
        "zeusaidesign.com",
    ]
    body = "\n".join(body_lines)

    msg = MIMEMultipart()
    msg["From"] = smtp_email
    msg["To"] = user_email
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=20) as server:
            server.login(smtp_email, smtp_password)
            server.sendmail(smtp_email, [user_email], msg.as_string())
        log.info("_send_task_email: sent to %s", user_email)
    except smtplib.SMTPAuthenticationError:
        log.warning("_send_task_email: Gmail auth failed — check SMTP_PASSWORD is an App Password")
    except smtplib.SMTPException as exc:
        log.warning("_send_task_email: SMTP error: %s", exc)

```

- [ ] **Step 4: Add `GET /tasks` endpoint to `main.py`**

In `backend/main.py`, find:
```python
# ── Existing REST endpoints ───────────────────────────────────────────────────

@app.get("/sessions")
```

Add before that block:

```python
# ── Tasks endpoints ───────────────────────────────────────────────────────────

@app.get("/tasks")
async def get_tasks(current_user: dict = Depends(auth.get_current_user)):
    plan = current_user.get("subscription_plan")
    status = current_user.get("subscription_status", "free")
    if not (status == "active" and plan == "enterprise"):
        raise HTTPException(status_code=403, detail="Enterprise plan required")
    db_path = db.get_db_path()
    return db.get_tasks_for_user(db_path, current_user["id"])

```

- [ ] **Step 5: Add `fail_stale_tasks` call to lifespan startup**

In `backend/main.py`, find the lifespan startup block:
```python
    try:
        _db_path = db.get_db_path()
        db.init_user_tables(_db_path)
        log.info("User tables initialised at %s", _db_path)
    except Exception:
        log.exception("FATAL: user table init failed")
        raise
```

Replace with:
```python
    try:
        _db_path = db.get_db_path()
        db.init_user_tables(_db_path)
        log.info("User tables initialised at %s", _db_path)
        db.fail_stale_tasks(_db_path)
        log.info("Stale running tasks marked as failed")
    except Exception:
        log.exception("FATAL: user table init failed")
        raise
```

- [ ] **Step 6: Run endpoint tests**

```bash
cd C:/Users/Student/zeus-app/backend
python -m pytest tests/test_tasks_endpoint.py -v
```

Expected: all 4 tests pass.

- [ ] **Step 7: Run full test suite to check for regressions**

```bash
cd C:/Users/Student/zeus-app/backend
python -m pytest tests/ -v
```

Expected: all tests pass.

- [ ] **Step 8: Commit**

```bash
cd C:/Users/Student/zeus-app
git add backend/main.py backend/tests/test_tasks_endpoint.py
git commit -m "feat: add /tasks endpoint, _send_task_email, and stale task cleanup"
```

---

### Task 4: Create `TasksPage.jsx`

**Files:**
- Create: `web/src/pages/TasksPage.jsx`

- [ ] **Step 1: Create the page**

Create `web/src/pages/TasksPage.jsx`:

```jsx
import { useEffect, useState, useCallback } from 'react';
import { Link } from 'react-router-dom';
import { Navbar } from '../components/Navbar';
import { useAuth } from '../contexts/AuthContext';

const BACKEND_URL = import.meta.env.VITE_BACKEND_URL || '';

const STATUS_BADGE = {
  pending: { label: '⏳ Pending',  className: 'badge-status badge-status--pending'  },
  running: { label: '🔄 Running',  className: 'badge-status badge-status--running'  },
  done:    { label: '✅ Done',     className: 'badge-status badge-status--done'     },
  failed:  { label: '❌ Failed',   className: 'badge-status badge-status--failed'   },
};

function TaskCard({ task }) {
  const badge = STATUS_BADGE[task.status] || STATUS_BADGE.pending;
  const createdAt = new Date(task.created_at).toLocaleString();

  return (
    <div className={`task-card task-card--${task.status}`}>
      <div className="task-card-header">
        <span className="task-description">{task.description}</span>
        <span className={badge.className}>{badge.label}</span>
      </div>
      <div className="task-card-meta">Started {createdAt}</div>
      {task.status === 'done' && task.live_url && (
        <a
          href={task.live_url}
          target="_blank"
          rel="noopener noreferrer"
          className="btn btn-primary btn-sm task-url-btn"
        >
          View Live Site →
        </a>
      )}
      {task.status === 'failed' && task.result && (
        <p className="task-error-note">{task.result.slice(0, 300)}</p>
      )}
    </div>
  );
}

export default function TasksPage() {
  const { user, token } = useAuth();
  const [tasks, setTasks] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const isEnterprise =
    user?.subscription_plan === 'enterprise' &&
    user?.subscription_status === 'active';

  const fetchTasks = useCallback(async () => {
    if (!token) return;
    try {
      const res = await fetch(`${BACKEND_URL}/tasks`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.status === 403) {
        setError('enterprise');
        return;
      }
      if (!res.ok) throw new Error('Failed to load tasks');
      const data = await res.json();
      setTasks(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => {
    fetchTasks();
  }, [fetchTasks]);

  // Poll every 10 seconds while any task is active
  useEffect(() => {
    const hasActive = tasks.some(
      (t) => t.status === 'pending' || t.status === 'running'
    );
    if (!hasActive) return;
    const id = setInterval(fetchTasks, 10_000);
    return () => clearInterval(id);
  }, [tasks, fetchTasks]);

  if (error === 'enterprise') {
    return (
      <div className="tasks-page">
        <Navbar />
        <div className="page tasks-page-inner">
          <h1 className="section-title">Background Tasks</h1>
          <div className="upgrade-gate">
            <p>Background tasks require an <strong>Enterprise</strong> plan.</p>
            <Link to="/pricing" className="btn btn-primary">Upgrade to Enterprise</Link>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="tasks-page">
      <Navbar />
      <div className="page tasks-page-inner">
        <div className="hero-orbs" aria-hidden>
          <div className="orb orb-1" />
          <div className="orb orb-2" />
        </div>

        <div className="section-label" style={{ textAlign: 'center' }}>Enterprise</div>
        <h1 className="section-title" style={{ textAlign: 'center', marginBottom: '0.5rem' }}>
          Background Tasks
        </h1>
        <p className="section-sub" style={{ textAlign: 'center', marginBottom: '2rem' }}>
          Long-running builds run in the background. You'll be emailed when they're done.
        </p>

        {error && error !== 'enterprise' && (
          <div className="form-error form-error--banner">{error}</div>
        )}

        {loading ? (
          <div style={{ textAlign: 'center', padding: '3rem' }}>
            <span className="spinner" />
          </div>
        ) : tasks.length === 0 ? (
          <div className="tasks-empty">
            <p className="tasks-empty-icon">⚡</p>
            <p className="tasks-empty-title">No background tasks yet.</p>
            <p className="tasks-empty-sub">
              Ask Zeus to build a website and it will appear here.
            </p>
          </div>
        ) : (
          <div className="tasks-list">
            {tasks.map((task) => (
              <TaskCard key={task.id} task={task} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Verify the file renders without import errors**

```bash
cd C:/Users/Student/zeus-app/web
node -e "const fs = require('fs'); const src = fs.readFileSync('src/pages/TasksPage.jsx', 'utf8'); console.log('Lines:', src.split('\n').length, '— OK')"
```

Expected: `Lines: <N> — OK`

- [ ] **Step 3: Add CSS for new classes**

In `web/src/index.css`, find the billing card styles section (search for `.billing-card`) and add after the billing styles:

```css
/* ── Tasks page ─────────────────────────────────────────────────── */
.tasks-page-inner { max-width: 760px; }

.tasks-list { display: flex; flex-direction: column; gap: 1rem; }

.task-card {
  background: rgba(255,255,255,0.04);
  border: 1px solid rgba(255,255,255,0.08);
  border-radius: 12px;
  padding: 1.25rem 1.5rem;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}
.task-card--running { border-color: rgba(167,139,250,0.4); }
.task-card--done    { border-color: rgba(52,211,153,0.35); }
.task-card--failed  { border-color: rgba(248,113,113,0.35); }

.task-card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  flex-wrap: wrap;
}
.task-description { color: #e2d9f3; font-weight: 600; font-size: 0.95rem; }
.task-card-meta   { color: #666; font-size: 0.78rem; }
.task-error-note  { color: #f87171; font-size: 0.8rem; margin-top: 0.25rem; }
.task-url-btn     { align-self: flex-start; margin-top: 0.25rem; }

.badge-status {
  font-size: 0.72rem;
  font-weight: 700;
  letter-spacing: 0.03em;
  padding: 0.25rem 0.6rem;
  border-radius: 999px;
  white-space: nowrap;
}
.badge-status--pending { background: rgba(251,191,36,0.15);  color: #fbbf24; }
.badge-status--running { background: rgba(167,139,250,0.15); color: #a78bfa; }
.badge-status--done    { background: rgba(52,211,153,0.15);  color: #34d399; }
.badge-status--failed  { background: rgba(248,113,113,0.15); color: #f87171; }

.tasks-empty {
  text-align: center;
  padding: 4rem 1rem;
}
.tasks-empty-icon  { font-size: 2.5rem; margin-bottom: 0.75rem; }
.tasks-empty-title { color: #e2d9f3; font-size: 1rem; font-weight: 600; margin-bottom: 0.25rem; }
.tasks-empty-sub   { color: #555; font-size: 0.85rem; }

.upgrade-gate {
  text-align: center;
  padding: 3rem 1rem;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 1.25rem;
}
.upgrade-gate p { color: #aaa; font-size: 1rem; }
```

- [ ] **Step 4: Commit**

```bash
cd C:/Users/Student/zeus-app
git add web/src/pages/TasksPage.jsx web/src/index.css
git commit -m "feat: add TasksPage with polling, status badges, and live URL button"
```

---

### Task 5: Wire up routing and Navbar link

**Files:**
- Modify: `web/src/App.jsx`
- Modify: `web/src/components/Navbar.jsx`

- [ ] **Step 1: Add `/tasks` route to `App.jsx`**

In `web/src/App.jsx`, find:
```jsx
import BillingPage from './pages/BillingPage';
```

Add after it:
```jsx
import TasksPage from './pages/TasksPage';
```

Then find:
```jsx
          <Route
            path="/billing"
            element={
              <ProtectedRoute>
                <BillingPage />
              </ProtectedRoute>
            }
          />
```

Add after it:
```jsx
          <Route
            path="/tasks"
            element={
              <ProtectedRoute>
                <TasksPage />
              </ProtectedRoute>
            }
          />
```

- [ ] **Step 2: Add Tasks nav link to `Navbar.jsx`**

In `web/src/components/Navbar.jsx`, find the logged-in section:
```jsx
          {user ? (
            <>
              <Link to="/dashboard" className="btn btn-sm btn-ghost">Dashboard</Link>
              <button className="btn btn-sm btn-outline" onClick={handleLogout}>
                Sign out
              </button>
            </>
```

Replace with:
```jsx
          {user ? (
            <>
              <Link to="/dashboard" className="btn btn-sm btn-ghost">Dashboard</Link>
              {user.subscription_plan === 'enterprise' && user.subscription_status === 'active' && (
                <Link to="/tasks" className="btn btn-sm btn-ghost">Tasks</Link>
              )}
              <button className="btn btn-sm btn-outline" onClick={handleLogout}>
                Sign out
              </button>
            </>
```

- [ ] **Step 3: Verify the web app builds without errors**

```bash
cd C:/Users/Student/zeus-app/web
npm run build 2>&1 | tail -10
```

Expected: output ends with `✓ built in` (Vite success message), no errors.

- [ ] **Step 4: Commit**

```bash
cd C:/Users/Student/zeus-app
git add web/src/App.jsx web/src/components/Navbar.jsx
git commit -m "feat: add /tasks route and enterprise nav link"
```

---

## Self-Review

### Spec coverage check

| Spec requirement | Task |
|---|---|
| `tasks` table (id, user_id, description, status, result, created_at, completed_at) | Task 1 |
| `live_url` column (Netlify URL) | Task 1 |
| `fail_stale_tasks` on startup | Task 3, Step 5 |
| Background worker via `asyncio.create_task` | Task 2, Step 5 |
| Enterprise gate on tool | Task 2, Step 5 |
| Email on completion via Gmail SMTP | Task 3, Step 3 |
| `GET /tasks` endpoint, enterprise-only 403 | Task 3, Step 4 |
| `CreateBackgroundTask` tool in TOOLS | Task 2, Step 2 |
| System prompt update | Task 2, Step 3 |
| `_bg_tasks` set for GC prevention | Task 2, Step 1 |
| `asyncio` import | Task 2, Step 6 |
| Tasks page with status badges | Task 4 |
| Polling while active tasks exist | Task 4, Step 1 |
| Live URL as clickable button | Task 4, Step 1 |
| Route `/tasks` | Task 5, Step 1 |
| Navbar Tasks link (enterprise only) | Task 5, Step 2 |

All requirements covered. ✓

### Placeholder scan

No TBDs, TODOs, or vague steps found. ✓

### Type consistency

- `db.create_task` returns `dict` → used as `task["id"]` in Task 2 ✓
- `db.update_task(db_path, task_id, **fields)` signature used consistently across Tasks 1–3 ✓
- `_send_task_email(user_email, description, live_url, result)` defined in Task 3 Step 3, called in Task 2 Step 5 ✓
- `run_multi_agent(request, on_message, history, user_id)` signature matches existing implementation ✓
