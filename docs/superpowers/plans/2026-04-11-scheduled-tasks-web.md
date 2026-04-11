# Scheduled Tasks (Backend + Web) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Allow Pro, Agency, and Enterprise users to schedule Zeus to automatically run a task on a recurring cron schedule, managed through a new "Scheduled Tasks" tab on the existing Tasks page.

**Architecture:** APScheduler `AsyncIOScheduler` in a new `scheduler.py` module runs async jobs directly in FastAPI's event loop. Five new API endpoints handle parse (with cache), create, list, delete, and toggle. The web frontend adds a two-tab layout to `TasksPage.jsx` and a new `ScheduledTasksTab.jsx` component.

**Tech Stack:** FastAPI, APScheduler 3.x (AsyncIOScheduler), croniter, SQLite (WAL), React 18, existing CSS custom properties

---

## File Map

| Action | File | Responsibility |
|---|---|---|
| Modify | `zeus-app/backend/requirements.txt` | Add apscheduler and croniter |
| Modify | `zeus-app/backend/db.py` | Add `scheduled_tasks` table + 7 DB functions |
| Create | `zeus-app/backend/tests/test_scheduled_tasks_db.py` | DB function unit tests |
| Create | `zeus-app/backend/scheduler.py` | AsyncIOScheduler, job management, `_run_scheduled_task` |
| Create | `zeus-app/backend/tests/test_scheduler.py` | `compute_next_run` unit test |
| Modify | `zeus-app/backend/main.py` | Plan gate helpers, parse cache, 5 endpoints, lifespan hooks |
| Create | `zeus-app/backend/tests/test_scheduled_tasks_api.py` | API endpoint tests |
| Modify | `zeus-app/web/src/pages/TasksPage.jsx` | Tab switcher, render ScheduledTasksTab |
| Create | `zeus-app/web/src/components/ScheduledTasksTab.jsx` | Full scheduled tasks UI |
| Modify | `zeus-app/web/src/index.css` | Tab switcher styles + scheduled task card styles |

---

### Task 1: Add dependencies to requirements.txt

**Files:**
- Modify: `zeus-app/backend/requirements.txt`

- [ ] **Step 1: Add apscheduler and croniter**

Open `zeus-app/backend/requirements.txt` and append:

```
apscheduler>=3.10.0
croniter>=2.0.0
```

The file should end with:

```
fpdf2>=2.7.0
python-docx>=1.1.0
apscheduler>=3.10.0
croniter>=2.0.0
```

- [ ] **Step 2: Install dependencies**

```bash
cd zeus-app/backend && pip install apscheduler>=3.10.0 croniter>=2.0.0
```

Expected: both packages install successfully.

- [ ] **Step 3: Commit**

```bash
cd zeus-app
git add backend/requirements.txt
git commit -m "feat: add apscheduler and croniter dependencies"
```

---

### Task 2: DB — scheduled_tasks table and functions

**Files:**
- Modify: `zeus-app/backend/db.py`
- Create: `zeus-app/backend/tests/test_scheduled_tasks_db.py`

- [ ] **Step 1: Write the failing tests**

Create `zeus-app/backend/tests/test_scheduled_tasks_db.py`:

```python
import os
import pathlib
import sys
import tempfile

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key-for-tests")


def _db(tmp_path):
    """Return a fresh db_path inside tmp_path."""
    import db
    db._db_initialised = False
    os.environ["ZEUS_DATA_DIR"] = str(tmp_path)
    path = db.get_db_path()
    db._db_initialised = False
    return path


class TestScheduledTasksDb:
    def test_create_and_get(self, tmp_path):
        import db
        db_path = _db(tmp_path)
        task = db.create_scheduled_task(
            db_path,
            user_id="user-1",
            task_description="Rebuild my website",
            cron_expression="0 9 * * 1",
            schedule_label="Every Monday at 9am",
            next_run="2026-04-14T09:00:00+00:00",
        )
        assert task["user_id"] == "user-1"
        assert task["task_description"] == "Rebuild my website"
        assert task["cron_expression"] == "0 9 * * 1"
        assert task["schedule_label"] == "Every Monday at 9am"
        assert task["is_active"] == 1
        assert task["last_run"] is None
        assert task["timezone"] == "UTC"
        assert "id" in task
        assert "created_at" in task

    def test_get_scheduled_tasks_for_user(self, tmp_path):
        import db
        db_path = _db(tmp_path)
        db.create_scheduled_task(db_path, "user-1", "Task A", "0 9 * * 1", "Mondays 9am", "2026-04-14T09:00:00+00:00")
        db.create_scheduled_task(db_path, "user-1", "Task B", "0 10 * * 2", "Tuesdays 10am", "2026-04-15T10:00:00+00:00")
        db.create_scheduled_task(db_path, "user-2", "Task C", "0 8 * * 3", "Wednesdays 8am", "2026-04-16T08:00:00+00:00")
        tasks = db.get_scheduled_tasks_for_user(db_path, "user-1")
        assert len(tasks) == 2
        # most recent first
        assert tasks[0]["task_description"] == "Task B"

    def test_get_all_active_scheduled_tasks(self, tmp_path):
        import db
        db_path = _db(tmp_path)
        t1 = db.create_scheduled_task(db_path, "user-1", "Task A", "0 9 * * 1", "Label", "2026-04-14T09:00:00+00:00")
        t2 = db.create_scheduled_task(db_path, "user-2", "Task B", "0 10 * * 2", "Label", "2026-04-15T10:00:00+00:00")
        db.update_scheduled_task(db_path, t1["id"], is_active=0)
        tasks = db.get_all_active_scheduled_tasks(db_path)
        assert len(tasks) == 1
        assert tasks[0]["id"] == t2["id"]

    def test_update_scheduled_task(self, tmp_path):
        import db
        db_path = _db(tmp_path)
        task = db.create_scheduled_task(db_path, "user-1", "Task", "0 9 * * 1", "Label", "2026-04-14T09:00:00+00:00")
        db.update_scheduled_task(db_path, task["id"], is_active=0, last_run="2026-04-14T09:00:01+00:00")
        updated = db.get_scheduled_task(db_path, task["id"])
        assert updated["is_active"] == 0
        assert updated["last_run"] == "2026-04-14T09:00:01+00:00"

    def test_delete_scheduled_task(self, tmp_path):
        import db
        db_path = _db(tmp_path)
        task = db.create_scheduled_task(db_path, "user-1", "Task", "0 9 * * 1", "Label", "2026-04-14T09:00:00+00:00")
        result = db.delete_scheduled_task(db_path, task["id"], "user-1")
        assert result is True
        assert db.get_scheduled_task(db_path, task["id"]) is None

    def test_delete_wrong_user_returns_false(self, tmp_path):
        import db
        db_path = _db(tmp_path)
        task = db.create_scheduled_task(db_path, "user-1", "Task", "0 9 * * 1", "Label", "2026-04-14T09:00:00+00:00")
        result = db.delete_scheduled_task(db_path, task["id"], "user-2")
        assert result is False
        assert db.get_scheduled_task(db_path, task["id"]) is not None

    def test_count_active_scheduled_tasks(self, tmp_path):
        import db
        db_path = _db(tmp_path)
        t1 = db.create_scheduled_task(db_path, "user-1", "Task A", "0 9 * * 1", "Label", "2026-04-14T09:00:00+00:00")
        db.create_scheduled_task(db_path, "user-1", "Task B", "0 10 * * 2", "Label", "2026-04-15T10:00:00+00:00")
        db.create_scheduled_task(db_path, "user-2", "Task C", "0 8 * * 3", "Label", "2026-04-16T08:00:00+00:00")
        db.update_scheduled_task(db_path, t1["id"], is_active=0)
        assert db.count_active_scheduled_tasks(db_path, "user-1") == 1
        assert db.count_active_scheduled_tasks(db_path, "user-2") == 1
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd zeus-app/backend && python -m pytest tests/test_scheduled_tasks_db.py -v
```

Expected: 7 failures — `AttributeError` because the functions don't exist yet.

- [ ] **Step 3: Add the scheduled_tasks table to `db.py`**

In `zeus-app/backend/db.py`, find the end of the `executescript` in `init_user_tables` (before the closing `"""`):

```python
            CREATE INDEX IF NOT EXISTS idx_tasks_user ON tasks (user_id);
        """)
```

Replace it with:

```python
            CREATE INDEX IF NOT EXISTS idx_tasks_user ON tasks (user_id);

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
        """)
```

- [ ] **Step 4: Add the 7 DB functions to `db.py`**

Append the following to the end of `zeus-app/backend/db.py`:

```python
# ── Scheduled Tasks ─────────────────────────────────────────────────────────


def create_scheduled_task(
    db_path: pathlib.Path,
    user_id: str,
    task_description: str,
    cron_expression: str,
    schedule_label: str,
    next_run: str,
    timezone: str = "UTC",
) -> dict:
    """Insert a new scheduled task and return the created row."""
    now = datetime.now(timezone.utc).isoformat()
    task_id = str(uuid.uuid4())
    conn = _conn(db_path)
    try:
        conn.execute(
            """
            INSERT INTO scheduled_tasks
                (id, user_id, task_description, cron_expression, schedule_label,
                 timezone, is_active, last_run, next_run, created_at)
            VALUES (?, ?, ?, ?, ?, ?, 1, NULL, ?, ?)
            """,
            (task_id, user_id, task_description, cron_expression, schedule_label,
             timezone, next_run, now),
        )
        conn.commit()
        return get_scheduled_task(db_path, task_id)
    finally:
        conn.close()


def get_scheduled_tasks_for_user(db_path: pathlib.Path, user_id: str) -> list[dict]:
    """Return all scheduled tasks for a user, most recent first."""
    conn = _conn(db_path)
    try:
        rows = conn.execute(
            "SELECT * FROM scheduled_tasks WHERE user_id = ? ORDER BY created_at DESC",
            (user_id,),
        ).fetchall()
        return [_row_to_dict(r) for r in rows]
    finally:
        conn.close()


def get_all_active_scheduled_tasks(db_path: pathlib.Path) -> list[dict]:
    """Return all rows where is_active = 1 — used by scheduler on startup."""
    conn = _conn(db_path)
    try:
        rows = conn.execute(
            "SELECT * FROM scheduled_tasks WHERE is_active = 1"
        ).fetchall()
        return [_row_to_dict(r) for r in rows]
    finally:
        conn.close()


def get_scheduled_task(db_path: pathlib.Path, task_id: str) -> dict | None:
    """Return a single scheduled task by ID."""
    conn = _conn(db_path)
    try:
        row = conn.execute(
            "SELECT * FROM scheduled_tasks WHERE id = ?", (task_id,)
        ).fetchone()
        return _row_to_dict(row)
    finally:
        conn.close()


def update_scheduled_task(db_path: pathlib.Path, task_id: str, **fields) -> None:
    """Update arbitrary columns on a scheduled task row."""
    if not fields:
        return
    set_clause = ", ".join(f"{k} = ?" for k in fields)
    values = list(fields.values()) + [task_id]
    conn = _conn(db_path)
    try:
        conn.execute(
            f"UPDATE scheduled_tasks SET {set_clause} WHERE id = ?", values
        )
        conn.commit()
    finally:
        conn.close()


def delete_scheduled_task(db_path: pathlib.Path, task_id: str, user_id: str) -> bool:
    """Delete a scheduled task owned by user_id. Returns True if deleted."""
    conn = _conn(db_path)
    try:
        cur = conn.execute(
            "DELETE FROM scheduled_tasks WHERE id = ? AND user_id = ?",
            (task_id, user_id),
        )
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def count_active_scheduled_tasks(db_path: pathlib.Path, user_id: str) -> int:
    """Count is_active = 1 rows for user — used for plan limit check."""
    conn = _conn(db_path)
    try:
        row = conn.execute(
            "SELECT COUNT(*) FROM scheduled_tasks WHERE user_id = ? AND is_active = 1",
            (user_id,),
        ).fetchone()
        return row[0] if row else 0
    finally:
        conn.close()
```

- [ ] **Step 5: Fix the `create_scheduled_task` timezone import collision**

The function signature uses `timezone` as a parameter name, which shadows `datetime.timezone`. In `create_scheduled_task`, change the line:

```python
    now = datetime.now(timezone.utc).isoformat()
```

to use the module-level import alias. Since `datetime` and `timezone` are already imported at the top of `db.py` as:

```python
from datetime import datetime, timezone
```

Rename the parameter to avoid the clash — change the function signature from `timezone: str = "UTC"` to `tz: str = "UTC"` and update the INSERT accordingly:

```python
def create_scheduled_task(
    db_path: pathlib.Path,
    user_id: str,
    task_description: str,
    cron_expression: str,
    schedule_label: str,
    next_run: str,
    tz: str = "UTC",
) -> dict:
    """Insert a new scheduled task and return the created row."""
    now = datetime.now(timezone.utc).isoformat()
    task_id = str(uuid.uuid4())
    conn = _conn(db_path)
    try:
        conn.execute(
            """
            INSERT INTO scheduled_tasks
                (id, user_id, task_description, cron_expression, schedule_label,
                 timezone, is_active, last_run, next_run, created_at)
            VALUES (?, ?, ?, ?, ?, ?, 1, NULL, ?, ?)
            """,
            (task_id, user_id, task_description, cron_expression, schedule_label,
             tz, next_run, now),
        )
        conn.commit()
        return get_scheduled_task(db_path, task_id)
    finally:
        conn.close()
```

- [ ] **Step 6: Run tests to verify they pass**

```bash
cd zeus-app/backend && python -m pytest tests/test_scheduled_tasks_db.py -v
```

Expected: 7 tests pass.

- [ ] **Step 7: Commit**

```bash
cd zeus-app
git add backend/db.py backend/tests/test_scheduled_tasks_db.py
git commit -m "feat: add scheduled_tasks table and DB functions"
```

---

### Task 3: Create `scheduler.py`

**Files:**
- Create: `zeus-app/backend/scheduler.py`
- Create: `zeus-app/backend/tests/test_scheduler.py`

- [ ] **Step 1: Write the failing test**

Create `zeus-app/backend/tests/test_scheduler.py`:

```python
import os
import pathlib
import sys
from datetime import datetime, timezone

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key-for-tests")


class TestComputeNextRun:
    def test_returns_iso_string_in_future(self):
        import scheduler
        result = scheduler.compute_next_run("0 9 * * 1")
        # Should parse as a valid ISO datetime
        dt = datetime.fromisoformat(result)
        assert dt > datetime.now(timezone.utc)

    def test_daily_schedule(self):
        import scheduler
        result = scheduler.compute_next_run("0 0 * * *")
        dt = datetime.fromisoformat(result)
        assert dt > datetime.now(timezone.utc)

    def test_invalid_cron_raises(self):
        import scheduler
        with pytest.raises(Exception):
            scheduler.compute_next_run("not a cron expression")
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd zeus-app/backend && python -m pytest tests/test_scheduler.py -v
```

Expected: 3 failures — `ModuleNotFoundError` because `scheduler.py` doesn't exist.

- [ ] **Step 3: Create `scheduler.py`**

Create `zeus-app/backend/scheduler.py`:

```python
"""
scheduler.py — APScheduler wrapper for Zeus scheduled tasks.

Uses AsyncIOScheduler so all jobs run as coroutines in FastAPI's event loop.
No thread pool is involved for async job functions, making concurrent SQLite
writes safe under WAL mode.

Public interface:
    init_scheduler(history_store)  — call in FastAPI lifespan startup
    shutdown_scheduler()           — call in FastAPI lifespan teardown
    add_job(task)                  — call after POST /scheduled-tasks
    remove_job(task_id)            — call after DELETE /scheduled-tasks/{id}
    set_job_enabled(task_id, active) — call after PATCH toggle
    compute_next_run(cron_expression) — returns next fire time as ISO string
"""
import logging
from datetime import datetime, timezone

log = logging.getLogger("zeus.scheduler")

_scheduler = None
_history = None  # set by init_scheduler; used by _run_scheduled_task


def compute_next_run(cron_expression: str) -> str:
    """Return the next fire time for a cron expression as an ISO datetime string (UTC)."""
    from croniter import croniter
    now = datetime.now(timezone.utc)
    return croniter(cron_expression, now).get_next(datetime).isoformat()


def init_scheduler(history_store) -> None:
    """Start the AsyncIOScheduler and load all active jobs from the DB."""
    global _scheduler, _history
    from apscheduler.schedulers.asyncio import AsyncIOScheduler
    import db

    _history = history_store
    _scheduler = AsyncIOScheduler()
    _scheduler.start()
    log.info("Scheduler started")

    db_path = db.get_db_path()
    tasks = db.get_all_active_scheduled_tasks(db_path)
    for task in tasks:
        add_job(task)
    log.info("Scheduler loaded %d active job(s) from DB", len(tasks))


def shutdown_scheduler() -> None:
    """Stop the scheduler gracefully."""
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        log.info("Scheduler shut down")
    _scheduler = None


def add_job(task: dict) -> None:
    """Add an APScheduler cron job for the given task dict."""
    if _scheduler is None:
        return
    from apscheduler.triggers.cron import CronTrigger

    task_id = task["id"]
    cron = task["cron_expression"]

    # Remove existing job with the same ID before adding (idempotent)
    if _scheduler.get_job(task_id):
        _scheduler.remove_job(task_id)

    trigger = CronTrigger.from_crontab(cron, timezone="UTC")
    _scheduler.add_job(
        _run_scheduled_task,
        trigger=trigger,
        id=task_id,
        args=[task_id],
        replace_existing=True,
        misfire_grace_time=3600,
    )
    log.info("Scheduler: added job %s (%s)", task_id, cron)


def remove_job(task_id: str) -> None:
    """Remove a scheduled job by task_id."""
    if _scheduler is None:
        return
    if _scheduler.get_job(task_id):
        _scheduler.remove_job(task_id)
        log.info("Scheduler: removed job %s", task_id)


def set_job_enabled(task_id: str, active: bool) -> None:
    """Pause or resume a scheduled job."""
    if _scheduler is None:
        return
    job = _scheduler.get_job(task_id)
    if active:
        if job:
            job.resume()
        # Job may not exist yet (was paused before a restart); re-add it from DB
        else:
            import db
            db_path = db.get_db_path()
            task = db.get_scheduled_task(db_path, task_id)
            if task:
                add_job(task)
        log.info("Scheduler: enabled job %s", task_id)
    else:
        if job:
            job.pause()
        log.info("Scheduler: paused job %s", task_id)


async def _run_scheduled_task(task_id: str) -> None:
    """Internal job runner. Always updates last_run/next_run in finally block."""
    import db
    from main import _handle_create_background_task

    db_path = db.get_db_path()
    task = db.get_scheduled_task(db_path, task_id)
    if not task or not task["is_active"]:
        return
    user = db.get_user_by_id(db_path, task["user_id"])
    if not user:
        log.warning("_run_scheduled_task: user %s not found for task %s", task["user_id"], task_id)
        return

    log.info("_run_scheduled_task: firing task %s for user %s", task_id, task["user_id"])
    try:
        await _handle_create_background_task(
            request=task["task_description"],
            description=task["task_description"],
            history=_history,
            user_id=task["user_id"],
        )
    except Exception:
        log.exception("_run_scheduled_task: task %s raised unexpectedly", task_id)
    finally:
        # Always advance the schedule — a failed run must not freeze next_run
        now = datetime.now(timezone.utc).isoformat()
        next_run = compute_next_run(task["cron_expression"])
        db.update_scheduled_task(db_path, task_id, last_run=now, next_run=next_run)
        log.info("_run_scheduled_task: task %s completed, next_run=%s", task_id, next_run)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd zeus-app/backend && python -m pytest tests/test_scheduler.py -v
```

Expected: 3 tests pass.

- [ ] **Step 5: Commit**

```bash
cd zeus-app
git add backend/scheduler.py backend/tests/test_scheduler.py
git commit -m "feat: add scheduler.py with AsyncIOScheduler"
```

---

### Task 4: API — plan gate helpers and parse endpoint

**Files:**
- Modify: `zeus-app/backend/main.py`
- Create: `zeus-app/backend/tests/test_scheduled_tasks_api.py`

- [ ] **Step 1: Write the failing tests (parse endpoint)**

Create `zeus-app/backend/tests/test_scheduled_tasks_api.py`:

```python
import os
import pathlib
import sys
from unittest.mock import patch, AsyncMock, MagicMock

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key-for-tests")


def _pro_user():
    return {
        "id": "pro-user-1",
        "email": "pro@example.com",
        "subscription_status": "active",
        "subscription_plan": "pro",
        "password_hash": "x",
        "name": "Pro User",
        "is_admin": 0,
    }


def _agency_user():
    return {
        "id": "agency-user-1",
        "email": "agency@example.com",
        "subscription_status": "active",
        "subscription_plan": "agency",
        "password_hash": "x",
        "name": "Agency User",
        "is_admin": 0,
    }


def _enterprise_user():
    return {
        "id": "ent-user-1",
        "email": "ent@example.com",
        "subscription_status": "active",
        "subscription_plan": "enterprise",
        "password_hash": "x",
        "name": "Ent User",
        "is_admin": 0,
    }


def _free_user():
    return {
        "id": "free-user-1",
        "email": "free@example.com",
        "subscription_status": "free",
        "subscription_plan": None,
        "password_hash": "x",
        "name": "Free User",
        "is_admin": 0,
    }


def _admin_user():
    return {
        "id": "admin-1",
        "email": "admin@example.com",
        "subscription_status": "active",
        "subscription_plan": "enterprise",
        "password_hash": "x",
        "name": "Admin",
        "is_admin": 1,
    }


class TestScheduledTasksPlanGate:
    def test_free_user_cannot_list(self):
        import auth
        from main import app
        from fastapi.testclient import TestClient
        app.dependency_overrides[auth.get_current_user] = _free_user
        try:
            with TestClient(app) as client:
                resp = client.get("/scheduled-tasks", headers={"Authorization": "Bearer fake"})
                assert resp.status_code == 403
        finally:
            app.dependency_overrides.pop(auth.get_current_user, None)

    def test_pro_user_can_list(self):
        import auth
        import db
        from main import app
        from fastapi.testclient import TestClient
        app.dependency_overrides[auth.get_current_user] = _pro_user
        try:
            with patch.object(db, "get_scheduled_tasks_for_user", return_value=[]):
                with TestClient(app) as client:
                    resp = client.get("/scheduled-tasks", headers={"Authorization": "Bearer fake"})
                    assert resp.status_code == 200
                    assert resp.json() == []
        finally:
            app.dependency_overrides.pop(auth.get_current_user, None)

    def test_admin_bypasses_plan_gate(self):
        import auth
        import db
        from main import app
        from fastapi.testclient import TestClient
        app.dependency_overrides[auth.get_current_user] = _admin_user
        try:
            with patch.object(db, "get_scheduled_tasks_for_user", return_value=[]):
                with TestClient(app) as client:
                    resp = client.get("/scheduled-tasks", headers={"Authorization": "Bearer fake"})
                    assert resp.status_code == 200
        finally:
            app.dependency_overrides.pop(auth.get_current_user, None)


class TestParseEndpoint:
    def _mock_anthropic_parse(self, natural_language, cron, label):
        """Helper: mock Anthropic client to return a cron JSON response."""
        mock_msg = MagicMock()
        mock_msg.content = [MagicMock(text=f'{{"cron_expression": "{cron}", "schedule_label": "{label}"}}')]
        mock_client = MagicMock()
        mock_client.messages.create = MagicMock(return_value=mock_msg)
        return mock_client

    def test_parse_returns_cron(self):
        import auth
        from main import app, _parse_cache
        from fastapi.testclient import TestClient
        _parse_cache.clear()
        app.dependency_overrides[auth.get_current_user] = _pro_user
        mock_client = self._mock_anthropic_parse("every monday at 9am", "0 9 * * 1", "Every Monday at 9am")
        try:
            with patch("main.get_anthropic_client", return_value=mock_client):
                with TestClient(app) as client:
                    resp = client.post(
                        "/scheduled-tasks/parse",
                        json={"natural_language": "every monday at 9am"},
                        headers={"Authorization": "Bearer fake"},
                    )
                    assert resp.status_code == 200
                    data = resp.json()
                    assert data["cron_expression"] == "0 9 * * 1"
                    assert data["schedule_label"] == "Every Monday at 9am"
        finally:
            app.dependency_overrides.pop(auth.get_current_user, None)
            _parse_cache.clear()

    def test_parse_uses_cache(self):
        import auth
        from main import app, _parse_cache
        from fastapi.testclient import TestClient
        _parse_cache.clear()
        _parse_cache["every monday at 9am"] = {"cron_expression": "0 9 * * 1", "schedule_label": "Every Monday at 9am"}
        app.dependency_overrides[auth.get_current_user] = _pro_user
        try:
            with TestClient(app) as client:
                # No mock needed — cache hit should not call Anthropic
                resp = client.post(
                    "/scheduled-tasks/parse",
                    json={"natural_language": "every monday at 9am"},
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 200
                assert resp.json()["cron_expression"] == "0 9 * * 1"
        finally:
            app.dependency_overrides.pop(auth.get_current_user, None)
            _parse_cache.clear()

    def test_parse_returns_400_on_claude_error(self):
        import auth
        from main import app, _parse_cache
        from fastapi.testclient import TestClient
        _parse_cache.clear()
        mock_msg = MagicMock()
        mock_msg.content = [MagicMock(text='{"error": "Could not parse schedule"}')]
        mock_client = MagicMock()
        mock_client.messages.create = MagicMock(return_value=mock_msg)
        app.dependency_overrides[auth.get_current_user] = _pro_user
        try:
            with patch("main.get_anthropic_client", return_value=mock_client):
                with TestClient(app) as client:
                    resp = client.post(
                        "/scheduled-tasks/parse",
                        json={"natural_language": "potato"},
                        headers={"Authorization": "Bearer fake"},
                    )
                    assert resp.status_code == 400
        finally:
            app.dependency_overrides.pop(auth.get_current_user, None)
            _parse_cache.clear()

    def test_free_user_can_parse(self):
        """Parse endpoint has no plan gate — free users can preview."""
        import auth
        from main import app, _parse_cache
        from fastapi.testclient import TestClient
        _parse_cache.clear()
        app.dependency_overrides[auth.get_current_user] = _free_user
        mock_msg = MagicMock()
        mock_msg.content = [MagicMock(text='{"cron_expression": "0 9 * * 1", "schedule_label": "Every Monday at 9am"}')]
        mock_client = MagicMock()
        mock_client.messages.create = MagicMock(return_value=mock_msg)
        try:
            with patch("main.get_anthropic_client", return_value=mock_client):
                with TestClient(app) as client:
                    resp = client.post(
                        "/scheduled-tasks/parse",
                        json={"natural_language": "every monday"},
                        headers={"Authorization": "Bearer fake"},
                    )
                    assert resp.status_code == 200
        finally:
            app.dependency_overrides.pop(auth.get_current_user, None)
            _parse_cache.clear()
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd zeus-app/backend && python -m pytest tests/test_scheduled_tasks_api.py::TestScheduledTasksPlanGate tests/test_scheduled_tasks_api.py::TestParseEndpoint -v
```

Expected: failures — 404 responses because endpoints don't exist.

- [ ] **Step 3: Add plan gate helpers and parse cache to `main.py`**

In `main.py`, find the line `history: HistoryStore | None = None` (around line 174). Add after it:

```python
_parse_cache: dict[str, dict] = {}

_SCHEDULED_TASK_LIMITS = {"pro": 5, "agency": 20, "enterprise": None}


def _scheduled_task_plan_allowed(user: dict) -> bool:
    """Return True if user's plan includes scheduled tasks."""
    plan = user.get("subscription_plan")
    status = user.get("subscription_status", "free")
    is_admin = bool(user.get("is_admin", 0))
    return is_admin or (status == "active" and plan in _SCHEDULED_TASK_LIMITS)


def _scheduled_task_limit(user: dict) -> int | None:
    """Return max active scheduled tasks for user's plan, or None for unlimited."""
    if user.get("is_admin"):
        return None
    return _SCHEDULED_TASK_LIMITS.get(user.get("subscription_plan"))
```

- [ ] **Step 4: Add the parse endpoint to `main.py`**

Find the `GET /admin/credits` endpoint block in `main.py` and add the following after it (before the `/tasks` endpoints):

```python
# ── Scheduled Tasks ─────────────────────────────────────────────────────────

class ScheduledTaskParseRequest(BaseModel):
    natural_language: str


@app.post("/scheduled-tasks/parse")
async def parse_scheduled_task(
    body: ScheduledTaskParseRequest,
    current_user: dict = Depends(auth.get_current_user),
):
    """Parse a natural language schedule into a cron expression. No plan gate."""
    key = body.natural_language.lower().strip()
    if key in _parse_cache:
        return _parse_cache[key]

    client = get_anthropic_client()
    try:
        msg = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=128,
            system=(
                "You extract cron expressions from natural language schedule descriptions. "
                'Respond with ONLY a JSON object: {"cron_expression": "...", "schedule_label": "..."}\n'
                "- cron_expression: standard 5-field cron (minute hour day month weekday)\n"
                '- schedule_label: concise human-readable label, e.g. "Every Monday at 9am"\n'
                "If you cannot parse the input into a valid cron expression, respond with:\n"
                '{"error": "Could not parse schedule — try something like \'every Monday at 9am\'"}\n'
                "Do not include any other text."
            ),
            messages=[{"role": "user", "content": body.natural_language}],
        )
    except Exception:
        log.exception("parse_scheduled_task: Anthropic call failed")
        raise HTTPException(status_code=400, detail="Schedule parsing timed out — try again")

    import json as _json
    try:
        result = _json.loads(msg.content[0].text)
    except Exception:
        raise HTTPException(status_code=400, detail="Could not parse schedule — try again")

    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])

    _parse_cache[key] = result
    return result
```

- [ ] **Step 5: Add the GET /scheduled-tasks list endpoint to `main.py`**

Immediately after the parse endpoint, add:

```python
@app.get("/scheduled-tasks")
async def list_scheduled_tasks(
    db_path: pathlib.Path = Depends(db.get_db_path_dep),
    current_user: dict = Depends(auth.get_current_user),
):
    if not _scheduled_task_plan_allowed(current_user):
        raise HTTPException(status_code=403, detail="Scheduled tasks require a Pro plan or above.")
    return db.get_scheduled_tasks_for_user(db_path, current_user["id"])
```

- [ ] **Step 6: Run parse + list tests to verify they pass**

```bash
cd zeus-app/backend && python -m pytest tests/test_scheduled_tasks_api.py::TestScheduledTasksPlanGate tests/test_scheduled_tasks_api.py::TestParseEndpoint -v
```

Expected: 7 tests pass.

- [ ] **Step 7: Commit**

```bash
cd zeus-app
git add backend/main.py backend/tests/test_scheduled_tasks_api.py
git commit -m "feat: add scheduled tasks plan gate helpers and parse endpoint"
```

---

### Task 5: API — create, delete, and toggle endpoints

**Files:**
- Modify: `zeus-app/backend/main.py`
- Modify: `zeus-app/backend/tests/test_scheduled_tasks_api.py`

- [ ] **Step 1: Add failing tests for CRUD endpoints**

Append the following classes to `zeus-app/backend/tests/test_scheduled_tasks_api.py`:

```python
class TestCreateScheduledTask:
    def _task_row(self, **kwargs):
        base = {
            "id": "task-1",
            "user_id": "pro-user-1",
            "task_description": "Rebuild site",
            "cron_expression": "0 9 * * 1",
            "schedule_label": "Every Monday at 9am",
            "timezone": "UTC",
            "is_active": 1,
            "last_run": None,
            "next_run": "2026-04-14T09:00:00+00:00",
            "created_at": "2026-04-11T12:00:00+00:00",
        }
        base.update(kwargs)
        return base

    def test_pro_user_can_create(self):
        import auth
        import db
        import scheduler as _sched
        from main import app
        from fastapi.testclient import TestClient
        app.dependency_overrides[auth.get_current_user] = _pro_user
        task_row = self._task_row()
        try:
            with patch.object(db, "count_active_scheduled_tasks", return_value=0), \
                 patch.object(db, "create_scheduled_task", return_value=task_row), \
                 patch.object(_sched, "add_job") as mock_add:
                with TestClient(app) as client:
                    resp = client.post(
                        "/scheduled-tasks",
                        json={
                            "task_description": "Rebuild site",
                            "cron_expression": "0 9 * * 1",
                            "schedule_label": "Every Monday at 9am",
                            "timezone": "UTC",
                        },
                        headers={"Authorization": "Bearer fake"},
                    )
                    assert resp.status_code == 200
                    assert resp.json()["id"] == "task-1"
                    mock_add.assert_called_once()
        finally:
            app.dependency_overrides.pop(auth.get_current_user, None)

    def test_free_user_cannot_create(self):
        import auth
        from main import app
        from fastapi.testclient import TestClient
        app.dependency_overrides[auth.get_current_user] = _free_user
        try:
            with TestClient(app) as client:
                resp = client.post(
                    "/scheduled-tasks",
                    json={
                        "task_description": "Rebuild site",
                        "cron_expression": "0 9 * * 1",
                        "schedule_label": "Label",
                        "timezone": "UTC",
                    },
                    headers={"Authorization": "Bearer fake"},
                )
                assert resp.status_code == 403
        finally:
            app.dependency_overrides.pop(auth.get_current_user, None)

    def test_pro_user_at_limit_cannot_create(self):
        import auth
        import db
        from main import app
        from fastapi.testclient import TestClient
        app.dependency_overrides[auth.get_current_user] = _pro_user
        try:
            with patch.object(db, "count_active_scheduled_tasks", return_value=5):
                with TestClient(app) as client:
                    resp = client.post(
                        "/scheduled-tasks",
                        json={
                            "task_description": "Rebuild site",
                            "cron_expression": "0 9 * * 1",
                            "schedule_label": "Label",
                            "timezone": "UTC",
                        },
                        headers={"Authorization": "Bearer fake"},
                    )
                    assert resp.status_code == 403
                    assert "5" in resp.json()["detail"]
        finally:
            app.dependency_overrides.pop(auth.get_current_user, None)

    def test_invalid_cron_returns_400(self):
        import auth
        import db
        from main import app
        from fastapi.testclient import TestClient
        app.dependency_overrides[auth.get_current_user] = _pro_user
        try:
            with patch.object(db, "count_active_scheduled_tasks", return_value=0):
                with TestClient(app) as client:
                    resp = client.post(
                        "/scheduled-tasks",
                        json={
                            "task_description": "Rebuild site",
                            "cron_expression": "not valid",
                            "schedule_label": "Label",
                            "timezone": "UTC",
                        },
                        headers={"Authorization": "Bearer fake"},
                    )
                    assert resp.status_code == 400
        finally:
            app.dependency_overrides.pop(auth.get_current_user, None)

    def test_enterprise_user_unlimited(self):
        import auth
        import db
        import scheduler as _sched
        from main import app
        from fastapi.testclient import TestClient
        app.dependency_overrides[auth.get_current_user] = _enterprise_user
        task_row = self._task_row(user_id="ent-user-1")
        try:
            with patch.object(db, "count_active_scheduled_tasks", return_value=999), \
                 patch.object(db, "create_scheduled_task", return_value=task_row), \
                 patch.object(_sched, "add_job"):
                with TestClient(app) as client:
                    resp = client.post(
                        "/scheduled-tasks",
                        json={
                            "task_description": "Rebuild site",
                            "cron_expression": "0 9 * * 1",
                            "schedule_label": "Label",
                            "timezone": "UTC",
                        },
                        headers={"Authorization": "Bearer fake"},
                    )
                    assert resp.status_code == 200
        finally:
            app.dependency_overrides.pop(auth.get_current_user, None)


class TestDeleteScheduledTask:
    def test_delete_owned_task(self):
        import auth
        import db
        import scheduler as _sched
        from main import app
        from fastapi.testclient import TestClient
        app.dependency_overrides[auth.get_current_user] = _pro_user
        try:
            with patch.object(db, "delete_scheduled_task", return_value=True), \
                 patch.object(_sched, "remove_job") as mock_remove:
                with TestClient(app) as client:
                    resp = client.delete(
                        "/scheduled-tasks/task-1",
                        headers={"Authorization": "Bearer fake"},
                    )
                    assert resp.status_code == 200
                    assert resp.json() == {"ok": True}
                    mock_remove.assert_called_once_with("task-1")
        finally:
            app.dependency_overrides.pop(auth.get_current_user, None)

    def test_delete_not_owned_returns_404(self):
        import auth
        import db
        from main import app
        from fastapi.testclient import TestClient
        app.dependency_overrides[auth.get_current_user] = _pro_user
        try:
            with patch.object(db, "delete_scheduled_task", return_value=False):
                with TestClient(app) as client:
                    resp = client.delete(
                        "/scheduled-tasks/task-999",
                        headers={"Authorization": "Bearer fake"},
                    )
                    assert resp.status_code == 404
        finally:
            app.dependency_overrides.pop(auth.get_current_user, None)


class TestToggleScheduledTask:
    def _task_row(self, is_active):
        return {
            "id": "task-1",
            "user_id": "pro-user-1",
            "task_description": "Rebuild site",
            "cron_expression": "0 9 * * 1",
            "schedule_label": "Every Monday at 9am",
            "timezone": "UTC",
            "is_active": is_active,
            "last_run": None,
            "next_run": "2026-04-14T09:00:00+00:00",
            "created_at": "2026-04-11T12:00:00+00:00",
        }

    def test_deactivate_task(self):
        import auth
        import db
        import scheduler as _sched
        from main import app
        from fastapi.testclient import TestClient
        active_task = self._task_row(is_active=1)
        paused_task = self._task_row(is_active=0)
        app.dependency_overrides[auth.get_current_user] = _pro_user
        try:
            with patch.object(db, "get_scheduled_task", side_effect=[active_task, paused_task]), \
                 patch.object(db, "update_scheduled_task"), \
                 patch.object(_sched, "set_job_enabled") as mock_toggle:
                with TestClient(app) as client:
                    resp = client.patch(
                        "/scheduled-tasks/task-1/toggle",
                        headers={"Authorization": "Bearer fake"},
                    )
                    assert resp.status_code == 200
                    assert resp.json()["is_active"] == 0
                    mock_toggle.assert_called_once_with("task-1", False)
        finally:
            app.dependency_overrides.pop(auth.get_current_user, None)

    def test_activate_task_at_limit_returns_403(self):
        import auth
        import db
        from main import app
        from fastapi.testclient import TestClient
        paused_task = self._task_row(is_active=0)
        app.dependency_overrides[auth.get_current_user] = _pro_user
        try:
            with patch.object(db, "get_scheduled_task", return_value=paused_task), \
                 patch.object(db, "count_active_scheduled_tasks", return_value=5):
                with TestClient(app) as client:
                    resp = client.patch(
                        "/scheduled-tasks/task-1/toggle",
                        headers={"Authorization": "Bearer fake"},
                    )
                    assert resp.status_code == 403
        finally:
            app.dependency_overrides.pop(auth.get_current_user, None)
```

- [ ] **Step 2: Run new tests to verify they fail**

```bash
cd zeus-app/backend && python -m pytest tests/test_scheduled_tasks_api.py::TestCreateScheduledTask tests/test_scheduled_tasks_api.py::TestDeleteScheduledTask tests/test_scheduled_tasks_api.py::TestToggleScheduledTask -v
```

Expected: failures — 404 or 405 responses.

- [ ] **Step 3: Add create, delete, and toggle endpoints to `main.py`**

After the `GET /scheduled-tasks` endpoint, add:

```python
class ScheduledTaskCreateRequest(BaseModel):
    task_description: str
    cron_expression: str
    schedule_label: str
    timezone: str = "UTC"


@app.post("/scheduled-tasks")
async def create_scheduled_task_endpoint(
    body: ScheduledTaskCreateRequest,
    db_path: pathlib.Path = Depends(db.get_db_path_dep),
    current_user: dict = Depends(auth.get_current_user),
):
    if not _scheduled_task_plan_allowed(current_user):
        raise HTTPException(status_code=403, detail="Scheduled tasks require a Pro plan or above.")

    limit = _scheduled_task_limit(current_user)
    if limit is not None:
        active_count = db.count_active_scheduled_tasks(db_path, current_user["id"])
        if active_count >= limit:
            plan = current_user.get("subscription_plan", "")
            raise HTTPException(
                status_code=403,
                detail=f"You've reached the limit of {limit} scheduled tasks on the {plan} plan. Upgrade to add more.",
            )

    # Validate cron expression
    try:
        from croniter import croniter
        if not croniter.is_valid(body.cron_expression):
            raise ValueError("invalid")
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid cron expression")

    import scheduler as _scheduler
    next_run = _scheduler.compute_next_run(body.cron_expression)
    task = db.create_scheduled_task(
        db_path,
        user_id=current_user["id"],
        task_description=body.task_description,
        cron_expression=body.cron_expression,
        schedule_label=body.schedule_label,
        next_run=next_run,
        tz=body.timezone,
    )
    _scheduler.add_job(task)
    return task


@app.delete("/scheduled-tasks/{task_id}")
async def delete_scheduled_task_endpoint(
    task_id: str,
    db_path: pathlib.Path = Depends(db.get_db_path_dep),
    current_user: dict = Depends(auth.get_current_user),
):
    if not _scheduled_task_plan_allowed(current_user):
        raise HTTPException(status_code=403, detail="Scheduled tasks require a Pro plan or above.")
    deleted = db.delete_scheduled_task(db_path, task_id, current_user["id"])
    if not deleted:
        raise HTTPException(status_code=404, detail="Task not found")
    import scheduler as _scheduler
    _scheduler.remove_job(task_id)
    return {"ok": True}


@app.patch("/scheduled-tasks/{task_id}/toggle")
async def toggle_scheduled_task(
    task_id: str,
    db_path: pathlib.Path = Depends(db.get_db_path_dep),
    current_user: dict = Depends(auth.get_current_user),
):
    if not _scheduled_task_plan_allowed(current_user):
        raise HTTPException(status_code=403, detail="Scheduled tasks require a Pro plan or above.")

    task = db.get_scheduled_task(db_path, task_id)
    if not task or task["user_id"] != current_user["id"]:
        raise HTTPException(status_code=404, detail="Task not found")

    new_active = 0 if task["is_active"] else 1

    if new_active == 1:
        # Re-activation limit check — prevents circumventing plan limits
        limit = _scheduled_task_limit(current_user)
        if limit is not None:
            active_count = db.count_active_scheduled_tasks(db_path, current_user["id"])
            if active_count >= limit:
                plan = current_user.get("subscription_plan", "")
                raise HTTPException(
                    status_code=403,
                    detail=f"You've reached the limit of {limit} scheduled tasks on the {plan} plan.",
                )

    import scheduler as _scheduler
    if new_active == 1:
        next_run = _scheduler.compute_next_run(task["cron_expression"])
        db.update_scheduled_task(db_path, task_id, is_active=1, next_run=next_run)
        _scheduler.set_job_enabled(task_id, True)
    else:
        db.update_scheduled_task(db_path, task_id, is_active=0)
        _scheduler.set_job_enabled(task_id, False)

    return db.get_scheduled_task(db_path, task_id)
```

- [ ] **Step 4: Run all scheduled tasks API tests**

```bash
cd zeus-app/backend && python -m pytest tests/test_scheduled_tasks_api.py -v
```

Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
cd zeus-app
git add backend/main.py backend/tests/test_scheduled_tasks_api.py
git commit -m "feat: add scheduled tasks CRUD and toggle endpoints"
```

---

### Task 6: Wire scheduler into `main.py` lifespan

**Files:**
- Modify: `zeus-app/backend/main.py`

- [ ] **Step 1: Add scheduler import to `main.py`**

Find the imports section at the top of `main.py` and add after the existing imports:

```python
import scheduler as _scheduler_mod
```

- [ ] **Step 2: Wire `init_scheduler` and `shutdown_scheduler` into the lifespan**

Find the lifespan function in `main.py`. It currently looks like:

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    global history
    ...
    if _RAILWAY:
        log.info("Running on Railway — skipping cloudflared tunnel (not installed)")
        yield
    else:
        port = int(os.environ.get("PORT", 8000))
        task = asyncio.create_task(start_tunnel_background(port))
        _background_tasks.add(task)
        task.add_done_callback(_background_tasks.discard)
        yield
        task.cancel()
        stop_tunnel()
```

Replace the entire `if _RAILWAY` / `else` block with:

```python
    _scheduler_mod.init_scheduler(history)
    log.info("Scheduler initialised")
    try:
        if _RAILWAY:
            log.info("Running on Railway — skipping cloudflared tunnel (not installed)")
            yield
        else:
            port = int(os.environ.get("PORT", 8000))
            task = asyncio.create_task(start_tunnel_background(port))
            _background_tasks.add(task)
            task.add_done_callback(_background_tasks.discard)
            yield
            task.cancel()
            stop_tunnel()
    finally:
        _scheduler_mod.shutdown_scheduler()
        log.info("Scheduler shut down")
```

- [ ] **Step 3: Run all backend tests to confirm no regressions**

```bash
cd zeus-app/backend && python -m pytest tests/ -v
```

Expected: all tests pass.

- [ ] **Step 4: Commit**

```bash
cd zeus-app
git add backend/main.py
git commit -m "feat: wire scheduler init/shutdown into FastAPI lifespan"
```

---

### Task 7: `TasksPage.jsx` tab switcher

**Files:**
- Modify: `zeus-app/web/src/pages/TasksPage.jsx`

- [ ] **Step 1: Update `TasksPage.jsx` with two-tab layout**

Replace the entire contents of `zeus-app/web/src/pages/TasksPage.jsx` with:

```jsx
import { useEffect, useState, useCallback } from 'react';
import { Link } from 'react-router-dom';
import { Navbar } from '../components/Navbar';
import { ScheduledTasksTab } from '../components/ScheduledTasksTab';
import { useAuth } from '../contexts/AuthContext';

const BACKEND_URL = import.meta.env.VITE_BACKEND_URL || '';

const STATUS_BADGE = {
  pending: { label: '⏳ Pending',  className: 'badge-status badge-status--pending'  },
  running: { label: '🔄 Running',  className: 'badge-status badge-status--running'  },
  done:    { label: '✅ Done',     className: 'badge-status badge-status--done'     },
  failed:  { label: '❌ Failed',   className: 'badge-status badge-status--failed'   },
};

function TaskCard({ task, onDelete }) {
  const badge = STATUS_BADGE[task.status] || STATUS_BADGE.pending;
  const createdAt = new Date(task.created_at).toLocaleString();

  return (
    <div className={`task-card task-card--${task.status}`}>
      <div className="task-card-header">
        <span className="task-description">{task.description}</span>
        <span className={badge.className}>{badge.label}</span>
        <button className="task-delete-btn" onClick={() => onDelete(task.id)} title="Delete task">✕</button>
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

function BackgroundTasksTab({ token }) {
  const [tasks, setTasks] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const handleDelete = useCallback(async (taskId) => {
    try {
      await fetch(`${BACKEND_URL}/tasks/${taskId}`, {
        method: 'DELETE',
        headers: { Authorization: `Bearer ${token}` },
      });
      setTasks((prev) => prev.filter((t) => t.id !== taskId));
    } catch {
      // silently ignore — task will reappear on next poll
    }
  }, [token]);

  const fetchTasks = useCallback(async () => {
    if (!token) return;
    try {
      const res = await fetch(`${BACKEND_URL}/tasks`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.status === 403) {
        setError('enterprise');
        setLoading(false);
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
      <div className="upgrade-gate">
        <p>Background tasks require an <strong>Enterprise</strong> plan.</p>
        <Link to="/pricing" className="btn btn-primary">Upgrade to Enterprise</Link>
      </div>
    );
  }

  if (error && error !== 'enterprise') {
    return <div className="form-error form-error--banner">{error}</div>;
  }

  if (loading) {
    return (
      <div style={{ textAlign: 'center', padding: '3rem' }}>
        <span className="spinner" />
      </div>
    );
  }

  if (tasks.length === 0) {
    return (
      <div className="tasks-empty">
        <p className="tasks-empty-icon">⚡</p>
        <p className="tasks-empty-title">No background tasks yet.</p>
        <p className="tasks-empty-sub">Ask Zeus to build a website and it will appear here.</p>
      </div>
    );
  }

  return (
    <div className="tasks-list">
      {tasks.map((task) => (
        <TaskCard key={task.id} task={task} onDelete={handleDelete} />
      ))}
    </div>
  );
}

export default function TasksPage() {
  const { token } = useAuth();
  const [activeTab, setActiveTab] = useState('background');

  return (
    <div className="tasks-page">
      <Navbar />
      <div className="page tasks-page-inner">
        <div className="hero-orbs" aria-hidden>
          <div className="orb orb-1" />
          <div className="orb orb-2" />
        </div>

        <h1 className="section-title" style={{ textAlign: 'center', marginBottom: '0.5rem' }}>
          Tasks
        </h1>

        <div className="tasks-tab-bar">
          <button
            className={`tasks-tab-btn${activeTab === 'background' ? ' tasks-tab-btn--active' : ''}`}
            onClick={() => setActiveTab('background')}
          >
            Background Tasks
          </button>
          <button
            className={`tasks-tab-btn${activeTab === 'scheduled' ? ' tasks-tab-btn--active' : ''}`}
            onClick={() => setActiveTab('scheduled')}
          >
            Scheduled Tasks
          </button>
        </div>

        {activeTab === 'background' && <BackgroundTasksTab token={token} />}
        {activeTab === 'scheduled' && <ScheduledTasksTab token={token} />}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
cd zeus-app
git add web/src/pages/TasksPage.jsx
git commit -m "feat: add tab switcher to TasksPage (Background / Scheduled Tasks)"
```

---

### Task 8: `ScheduledTasksTab.jsx` component

**Files:**
- Create: `zeus-app/web/src/components/ScheduledTasksTab.jsx`

- [ ] **Step 1: Create `ScheduledTasksTab.jsx`**

Create `zeus-app/web/src/components/ScheduledTasksTab.jsx`:

```jsx
import { useEffect, useState, useCallback } from 'react';
import { Link } from 'react-router-dom';

const BACKEND_URL = import.meta.env.VITE_BACKEND_URL || '';

function formatDateTime(iso) {
  if (!iso) return '—';
  return new Date(iso).toLocaleString();
}

function ScheduledTaskRow({ task, token, onToggle, onDelete }) {
  const [toggling, setToggling] = useState(false);
  const [deleting, setDeleting] = useState(false);

  const handleToggle = async () => {
    setToggling(true);
    try {
      const res = await fetch(`${BACKEND_URL}/scheduled-tasks/${task.id}/toggle`, {
        method: 'PATCH',
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const updated = await res.json();
      onToggle(updated);
    } catch {
      // revert optimistic update on error — parent handles state
    } finally {
      setToggling(false);
    }
  };

  const handleDelete = async () => {
    setDeleting(true);
    onDelete(task.id); // optimistic
    try {
      const res = await fetch(`${BACKEND_URL}/scheduled-tasks/${task.id}`, {
        method: 'DELETE',
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
    } catch {
      // revert: parent would need to re-fetch; for simplicity leave as deleted
    }
  };

  return (
    <div className={`scheduled-task-card${task.is_active ? '' : ' scheduled-task-card--paused'}`}>
      <div className="scheduled-task-card-header">
        <div className="scheduled-task-card-labels">
          <span className="scheduled-task-schedule-label">{task.schedule_label}</span>
          <span className={`scheduled-task-badge${task.is_active ? ' scheduled-task-badge--active' : ' scheduled-task-badge--paused'}`}>
            {task.is_active ? 'Active' : 'Paused'}
          </span>
        </div>
        <div className="scheduled-task-card-actions">
          <label className="scheduled-task-toggle" title={task.is_active ? 'Pause' : 'Activate'}>
            <input
              type="checkbox"
              checked={!!task.is_active}
              onChange={handleToggle}
              disabled={toggling}
            />
            <span className="scheduled-task-toggle-slider" />
          </label>
          <button
            className="task-delete-btn"
            onClick={handleDelete}
            disabled={deleting}
            title="Delete scheduled task"
          >
            ✕
          </button>
        </div>
      </div>
      <p className="scheduled-task-description">{task.task_description}</p>
      <div className="scheduled-task-meta">
        <span>Next run: {task.is_active ? formatDateTime(task.next_run) : '—'}</span>
        <span>Last run: {formatDateTime(task.last_run) || 'Never'}</span>
      </div>
    </div>
  );
}

export function ScheduledTasksTab({ token }) {
  const [tasks, setTasks] = useState([]);
  const [loading, setLoading] = useState(true);
  const [planError, setPlanError] = useState(false);
  const [fetchError, setFetchError] = useState('');

  // Create form state
  const [taskDesc, setTaskDesc] = useState('');
  const [scheduleInput, setScheduleInput] = useState('');
  const [parsedCron, setParsedCron] = useState(null); // {cron_expression, schedule_label}
  const [lastParsedInput, setLastParsedInput] = useState('');
  const [parsing, setParsing] = useState(false);
  const [parseError, setParseError] = useState('');
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState('');

  const fetchTasks = useCallback(async () => {
    if (!token) return;
    try {
      const res = await fetch(`${BACKEND_URL}/scheduled-tasks`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.status === 403) {
        setPlanError(true);
        setLoading(false);
        return;
      }
      if (!res.ok) throw new Error('Failed to load scheduled tasks');
      const data = await res.json();
      setTasks(data);
    } catch (err) {
      setFetchError(err.message);
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => {
    fetchTasks();
  }, [fetchTasks]);

  // Clear parse result if user edits the schedule input after parsing
  useEffect(() => {
    if (parsedCron && scheduleInput !== lastParsedInput) {
      setParsedCron(null);
    }
  }, [scheduleInput, parsedCron, lastParsedInput]);

  const handleParse = async () => {
    if (!scheduleInput.trim()) return;
    setParsing(true);
    setParseError('');
    setParsedCron(null);
    try {
      const res = await fetch(`${BACKEND_URL}/scheduled-tasks/parse`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ natural_language: scheduleInput }),
      });
      const data = await res.json();
      if (!res.ok) {
        setParseError(data.detail || 'Could not parse schedule');
        return;
      }
      setParsedCron(data);
      setLastParsedInput(scheduleInput);
    } catch {
      setParseError('Could not parse schedule — try again');
    } finally {
      setParsing(false);
    }
  };

  const handleCreate = async () => {
    if (!parsedCron || !taskDesc.trim()) return;
    setCreating(true);
    setCreateError('');
    try {
      const res = await fetch(`${BACKEND_URL}/scheduled-tasks`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          task_description: taskDesc,
          cron_expression: parsedCron.cron_expression,
          schedule_label: parsedCron.schedule_label,
          timezone: 'UTC',
        }),
      });
      const data = await res.json();
      if (!res.ok) {
        if (res.status === 403) {
          setCreateError(data.detail || 'Scheduled tasks require a Pro plan or above — upgrade at zeusaidesign.com/pricing.');
        } else {
          setCreateError(data.detail || 'Failed to create task');
        }
        return;
      }
      // Reset form and add new task at top
      setTaskDesc('');
      setScheduleInput('');
      setParsedCron(null);
      setLastParsedInput('');
      setTasks((prev) => [data, ...prev]);
    } catch {
      setCreateError('Failed to create task — try again');
    } finally {
      setCreating(false);
    }
  };

  const handleToggle = useCallback((updated) => {
    setTasks((prev) => prev.map((t) => (t.id === updated.id ? updated : t)));
  }, []);

  const handleDelete = useCallback((taskId) => {
    setTasks((prev) => prev.filter((t) => t.id !== taskId));
  }, []);

  if (planError) {
    return (
      <div className="upgrade-gate">
        <p>Scheduled tasks require a <strong>Pro plan</strong> or above.</p>
        <Link to="/pricing" className="btn btn-primary">Upgrade</Link>
      </div>
    );
  }

  return (
    <div className="scheduled-tasks-tab">
      {/* ── Create form ── */}
      <div className="scheduled-task-create-form">
        <h2 className="scheduled-task-create-title">Create Scheduled Task</h2>

        <textarea
          className="scheduled-task-textarea"
          placeholder="What should Zeus do? (e.g. Rebuild my bakery website)"
          value={taskDesc}
          onChange={(e) => setTaskDesc(e.target.value)}
          rows={3}
        />

        <div className="scheduled-task-parse-row">
          <input
            type="text"
            className="scheduled-task-schedule-input"
            placeholder="Describe your schedule (e.g. every Monday at 9am)"
            value={scheduleInput}
            onChange={(e) => setScheduleInput(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleParse()}
          />
          <button
            className="btn btn-secondary scheduled-task-parse-btn"
            onClick={handleParse}
            disabled={parsing || !scheduleInput.trim()}
          >
            {parsing ? <span className="spinner spinner--sm" /> : 'Parse ↺'}
          </button>
        </div>

        {parseError && (
          <div className="form-error">{parseError}</div>
        )}

        {parsedCron && (
          <div className="scheduled-task-parse-result">
            ✓ {parsedCron.schedule_label}
          </div>
        )}

        {parsedCron && (
          <button
            className="btn btn-primary"
            onClick={handleCreate}
            disabled={creating || !taskDesc.trim()}
          >
            {creating ? <span className="spinner spinner--sm" /> : 'Create Task'}
          </button>
        )}

        {createError && (
          <div className="form-error form-error--banner">{createError}</div>
        )}
      </div>

      {/* ── Task list ── */}
      {loading ? (
        <div style={{ textAlign: 'center', padding: '3rem' }}>
          <span className="spinner" />
        </div>
      ) : fetchError ? (
        <div className="form-error form-error--banner">{fetchError}</div>
      ) : tasks.length === 0 ? (
        <div className="tasks-empty">
          <p className="tasks-empty-icon">🗓</p>
          <p className="tasks-empty-title">No scheduled tasks yet.</p>
          <p className="tasks-empty-sub">Create one above.</p>
        </div>
      ) : (
        <div className="scheduled-tasks-list">
          {tasks.map((task) => (
            <ScheduledTaskRow
              key={task.id}
              task={task}
              token={token}
              onToggle={handleToggle}
              onDelete={handleDelete}
            />
          ))}
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
cd zeus-app
git add web/src/components/ScheduledTasksTab.jsx
git commit -m "feat: add ScheduledTasksTab component"
```

---

### Task 9: CSS — tab bar and scheduled task card styles

**Files:**
- Modify: `zeus-app/web/src/index.css`

- [ ] **Step 1: Add tab bar styles**

Find in `index.css`:

```css
.chat-window { flex: 1; display: flex; flex-direction: column; overflow: hidden; position: relative; }
```

After that line, or at the end of the file, append:

```css
/* ── Tasks tab bar ───────────────────────────────────────────── */
.tasks-tab-bar {
  display: flex;
  gap: 0.25rem;
  margin: 0 auto 2rem;
  background: var(--surface-2);
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 4px;
  width: fit-content;
}

.tasks-tab-btn {
  background: none;
  border: none;
  border-radius: 7px;
  padding: 0.45rem 1.1rem;
  font-size: 0.875rem;
  color: var(--text-muted);
  cursor: pointer;
  transition: background 0.15s, color 0.15s;
  white-space: nowrap;
}

.tasks-tab-btn:hover {
  color: var(--text);
}

.tasks-tab-btn--active {
  background: var(--accent);
  color: #000;
  font-weight: 600;
}

/* ── Scheduled tasks tab ─────────────────────────────────────── */
.scheduled-tasks-tab {
  display: flex;
  flex-direction: column;
  gap: 2rem;
}

.scheduled-task-create-form {
  background: var(--surface-2);
  border: 1px solid var(--border);
  border-radius: 14px;
  padding: 1.5rem;
  display: flex;
  flex-direction: column;
  gap: 0.875rem;
  max-width: 640px;
  margin: 0 auto;
  width: 100%;
}

.scheduled-task-create-title {
  font-size: 1rem;
  font-weight: 600;
  color: var(--text);
  margin: 0;
}

.scheduled-task-textarea {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 8px;
  color: var(--text);
  font-size: 0.9rem;
  padding: 0.6rem 0.75rem;
  resize: vertical;
  width: 100%;
  font-family: inherit;
}

.scheduled-task-textarea:focus {
  outline: none;
  border-color: var(--accent);
}

.scheduled-task-parse-row {
  display: flex;
  gap: 0.5rem;
}

.scheduled-task-schedule-input {
  flex: 1;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 8px;
  color: var(--text);
  font-size: 0.9rem;
  padding: 0.6rem 0.75rem;
}

.scheduled-task-schedule-input:focus {
  outline: none;
  border-color: var(--accent);
}

.scheduled-task-parse-btn {
  white-space: nowrap;
  min-width: 90px;
}

.scheduled-task-parse-result {
  color: var(--accent);
  font-size: 0.875rem;
  font-weight: 500;
}

/* ── Scheduled task cards ────────────────────────────────────── */
.scheduled-tasks-list {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  max-width: 640px;
  margin: 0 auto;
  width: 100%;
}

.scheduled-task-card {
  background: var(--surface-2);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 1rem 1.25rem;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.scheduled-task-card--paused {
  opacity: 0.65;
}

.scheduled-task-card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
}

.scheduled-task-card-labels {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex: 1;
  min-width: 0;
}

.scheduled-task-schedule-label {
  font-weight: 600;
  font-size: 0.9rem;
  color: var(--text);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.scheduled-task-badge {
  font-size: 0.7rem;
  font-weight: 600;
  padding: 2px 8px;
  border-radius: 20px;
  white-space: nowrap;
}

.scheduled-task-badge--active {
  background: rgba(0, 255, 65, 0.15);
  color: #00ff41;
}

.scheduled-task-badge--paused {
  background: var(--surface);
  color: var(--text-muted);
}

.scheduled-task-card-actions {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.scheduled-task-description {
  font-size: 0.85rem;
  color: var(--text-muted);
  margin: 0;
}

.scheduled-task-meta {
  display: flex;
  gap: 1.5rem;
  font-size: 0.75rem;
  color: var(--text-faint);
}

/* ── Toggle switch ───────────────────────────────────────────── */
.scheduled-task-toggle {
  position: relative;
  display: inline-block;
  width: 36px;
  height: 20px;
  cursor: pointer;
}

.scheduled-task-toggle input {
  opacity: 0;
  width: 0;
  height: 0;
  position: absolute;
}

.scheduled-task-toggle-slider {
  position: absolute;
  inset: 0;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 20px;
  transition: background 0.2s;
}

.scheduled-task-toggle-slider::before {
  content: '';
  position: absolute;
  width: 14px;
  height: 14px;
  left: 2px;
  top: 2px;
  background: var(--text-muted);
  border-radius: 50%;
  transition: transform 0.2s, background 0.2s;
}

.scheduled-task-toggle input:checked + .scheduled-task-toggle-slider {
  background: rgba(0, 255, 65, 0.2);
  border-color: var(--accent);
}

.scheduled-task-toggle input:checked + .scheduled-task-toggle-slider::before {
  transform: translateX(16px);
  background: var(--accent);
}
```

- [ ] **Step 2: Commit**

```bash
cd zeus-app
git add web/src/index.css
git commit -m "feat: add scheduled tasks tab bar and card styles"
```

---

### Task 10: Smoke test end-to-end

- [ ] **Step 1: Run all backend tests**

```bash
cd zeus-app/backend && python -m pytest tests/ -v
```

Expected: all tests pass, including the new scheduled tasks test files.

- [ ] **Step 2: Start the dev server**

```bash
cd zeus-app/web && npm run dev
```

- [ ] **Step 3: Verify tab switcher**

- Log in as any paid user account.
- Navigate to `/tasks`.
- Confirm two tabs are visible: **Background Tasks** and **Scheduled Tasks**.
- Clicking each tab should switch content without page reload.
- Default tab should be **Background Tasks** (existing content unchanged).

- [ ] **Step 4: Verify scheduled tasks form (paid user)**

- Switch to **Scheduled Tasks** tab.
- Enter a task description ("Rebuild my website").
- Enter a schedule ("every Tuesday at 8am").
- Click **Parse ↺** — a spinner appears, then disappears with "✓ Every Tuesday at 8am" confirmation.
- Editing the schedule input clears the confirmation.
- Click **Create Task** — task appears at top of list as Active.
- Toggle switch pauses the task (badge changes to grey "Paused", next run shows "—").
- Toggle again re-activates it.
- Delete button removes task from list immediately.

- [ ] **Step 5: Verify plan gate (free user)**

- Log in as a free user.
- Navigate to `/tasks` → **Scheduled Tasks** tab.
- Confirm the upgrade gate message appears ("Scheduled tasks require a Pro plan or above").
- Parse endpoint: free users CAN use Parse (no gate) — they just can't create.

- [ ] **Step 6: Verify Pro plan limit**

- If testing with a Pro account, create 5 tasks.
- On the 6th attempt, confirm the 403 error message is shown inline: "You've reached the limit of 5 scheduled tasks on the pro plan."
